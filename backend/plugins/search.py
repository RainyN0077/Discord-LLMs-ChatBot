# backend/plugins/search.py
import asyncio
import logging
import re
from typing import Dict, Any, Optional, Tuple, List
import discord
from tavily import TavilyClient

from .base import BasePlugin

logger = logging.getLogger(__name__)


class SearchPlugin(BasePlugin):
    """
    A plugin that uses the Tavily API to perform web searches and injects the results
    into the LLM context.
    """

    def __init__(self, plugin_config: Dict[str, Any], llm_provider_func=None):
        super().__init__(plugin_config, llm_provider_func)
        self.enabled = self.plugin_config.get("enabled", False)
        self.api_key = self.plugin_config.get("api_key")
        self.api_url = self.plugin_config.get("api_url")

        if self.enabled and not self.api_key:
            logger.warning("SearchPlugin is enabled but Tavily API key is missing.")
            self.enabled = False
            return

        self.client = None
        if self.enabled:
            self.client = TavilyClient(api_key=self.api_key, api_base_url=self.api_url)

        self.trigger_mode = self.plugin_config.get("trigger_mode", "command")
        self.command = self.plugin_config.get("command", "!search")
        self.keywords = self.plugin_config.get("keywords", [])

        self.search_depth = self.plugin_config.get("search_depth", "basic")
        self.require_main_trigger = bool(self.plugin_config.get("require_main_trigger", True))
        self.rewrite_query_with_llm = bool(self.plugin_config.get("rewrite_query_with_llm", True))
        try:
            self.max_results = max(1, int(self.plugin_config.get("max_results", 3)))
        except (TypeError, ValueError):
            self.max_results = 3

        self.include_date = bool(self.plugin_config.get("include_date", True))
        self.compression_strategy = self.plugin_config.get("compression_strategy", "none")
        self.include_domains = self.plugin_config.get("include_domains", [])
        self.exclude_domains = self.plugin_config.get("exclude_domains", [])

    async def _rewrite_query(self, query: str) -> str:
        """Use LLM to normalize user text into a concise search query."""
        if not self.rewrite_query_with_llm or not self.llm_caller:
            return query

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Rewrite user input into one concise web search query. "
                        "Output only the query text, without markdown or explanation."
                    ),
                },
                {"role": "user", "content": query},
            ]
            rewritten = await self.llm_caller(messages)
            cleaned = (rewritten or "").strip().strip('"').strip("'")
            if not cleaned:
                return query
            return cleaned[:220]
        except Exception as e:
            logger.warning(f"Search query rewrite failed, fallback to raw query. Error: {e}")
            return query

    async def handle_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        """Handles incoming messages and injects search results when triggered."""
        if not self.enabled:
            return None

        runtime_normal_triggered = bool(bot_config.get("_runtime_normal_triggered", False))
        if self.require_main_trigger and not runtime_normal_triggered:
            return None

        query = ""
        triggered = False

        if self.trigger_mode == "command":
            content = message.content or ""
            lowered = content.lower()
            cmd = (self.command or "").strip()
            cmd_lower = cmd.lower()
            if cmd_lower:
                # 1) Legacy mode: command at beginning, followed by space.
                if lowered.startswith(cmd_lower + " "):
                    query = content[len(cmd):].strip()
                    triggered = True
                else:
                    # 2) Robust mode: allow command inside sentence, separated by punctuation/spaces.
                    # Example: "Endless，搜索，帮我查查..." or "@Bot: search: latest ..."
                    pattern = re.compile(
                        rf"(^|[\\s,，:：]){re.escape(cmd_lower)}([\\s,，:：]+)(?P<q>.+)$"
                    )
                    m = pattern.search(lowered)
                    if m:
                        query = content[m.start("q"):].strip()
                        triggered = True
        elif self.trigger_mode == "keyword":
            for keyword in self.keywords:
                if keyword.lower() in message.content.lower():
                    query = message.content
                    triggered = True
                    logger.info(f"Search triggered by keyword: '{keyword}'")
                    break

        if not triggered:
            return None

        if not query:
            logger.warning(f"Search plugin triggered but query is empty. Message: {message.content}")
            return True

        final_query = await self._rewrite_query(query)

        try:
            logger.info(f"Performing Tavily search for query: '{final_query}'")
            search_result = await asyncio.to_thread(
                self.client.search,
                query=final_query,
                search_depth=self.search_depth,
                max_results=self.max_results,
                include_domains=self.include_domains,
                exclude_domains=self.exclude_domains,
            )
        except Exception as e:
            logger.error(f"Tavily API error: {e}", exc_info=True)
            await message.reply(f"Sorry, I encountered an error while searching: {e}", mention_author=False)
            return True

        if not search_result or not search_result.get("results"):
            logger.info("Tavily search returned no results.")
            return None

        formatted_results = self.format_results(search_result, final_query)
        logger.info("Injecting search results into LLM context.")
        return "append", [formatted_results]

    def _compress_with_rag(self, content: str, query: str, max_chars: int = 420) -> str:
        """
        A lightweight RAG-style compression:
        1) Split content into sentences/chunks.
        2) Score each chunk by overlap with query terms.
        3) Return top chunks within char budget.
        """
        text = (content or "").strip()
        if not text:
            return "No content available."

        query_terms = set(
            term.lower() for term in re.findall(r"\w+", query or "")
            if len(term) >= 2
        )

        chunks = [c.strip() for c in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if c and c.strip()]
        if not chunks:
            chunks = [text]

        scored_chunks: List[Tuple[int, int, str]] = []
        for idx, chunk in enumerate(chunks):
            chunk_terms = set(re.findall(r"\w+", chunk.lower()))
            overlap = len(query_terms & chunk_terms) if query_terms else 0
            length_bonus = 1 if 40 <= len(chunk) <= 260 else 0
            score = overlap * 10 + length_bonus
            scored_chunks.append((score, idx, chunk))

        scored_chunks.sort(key=lambda item: (-item[0], item[1]))

        selected: List[str] = []
        total = 0
        for score, _, chunk in scored_chunks:
            if score <= 0 and selected:
                continue

            next_len = len(chunk) + (1 if selected else 0)
            if total + next_len > max_chars:
                continue
            selected.append(chunk)
            total += next_len
            if total >= max_chars * 0.85:
                break

        if not selected:
            return text[:max_chars].rstrip() + ("..." if len(text) > max_chars else "")

        return " ".join(selected).strip()

    def format_results(self, search_result: Dict[str, Any], query: str = "") -> str:
        """Formats search results for context injection."""
        snippets = []
        for result in search_result.get("results", []):
            content = result.get("content", "No content available.")

            if self.compression_strategy == "truncate" and len(content) > 320:
                content = content[:320].rstrip() + "..."
            elif self.compression_strategy == "rag":
                content = self._compress_with_rag(content, query, max_chars=420)

            published = ""
            if self.include_date:
                published_raw = result.get("published_date") or result.get("date")
                if published_raw:
                    published = f"\n  - Date: {published_raw}"

            snippet = (
                f"- **{result.get('title', 'No Title')}** ([Source]({result.get('url', '#')}))\n"
                f"  - Content: {content}{published}"
            )
            snippets.append(snippet)

        if not snippets:
            return "No information found from the web search."

        return "Web Search Results (for your reference):\n" + "\n".join(snippets)
