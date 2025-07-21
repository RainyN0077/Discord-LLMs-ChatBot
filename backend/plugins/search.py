# backend/plugins/search.py
import logging
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
        
        if self.enabled and not self.api_key:
            logger.warning("SearchPlugin is enabled but Tavily API key is missing.")
            self.enabled = False
            return
            
        self.client = TavilyClient(api_key=self.api_key)
        self.command = self.plugin_config.get("command", "!search")
        self.search_depth = self.plugin_config.get("search_depth", "basic")
        self.max_results = self.plugin_config.get("max_results", 3)
        self.include_domains = self.plugin_config.get("include_domains", [])
        self.exclude_domains = self.plugin_config.get("exclude_domains", [])

    async def handle_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        """
        Handles incoming messages to check for the search command.
        """
        if not self.enabled or not message.content.lower().startswith(self.command + " "):
            return None

        query = message.content[len(self.command):].strip()
        if not query:
            # Maybe send a help message back to the user
            # await message.reply("Please provide a search query after the command.", mention_author=False)
            return True # Indicates we've handled the message and no further action is needed

        try:
            logger.info(f"Performing Tavily search for query: '{query}'")
            # Using async client would be better if Tavily supported it in their python lib.
            # For now, we run the sync search in a thread to avoid blocking.
            search_result = await discord.utils.async_dispatch(
                self.client.search,
                query,
                search_depth=self.search_depth,
                max_results=self.max_results,
                include_domains=self.include_domains,
                exclude_domains=self.exclude_domains
            )
        except Exception as e:
            logger.error(f"Tavily API error: {e}", exc_info=True)
            # Notify the user of the error
            await message.reply(f"Sorry, I encountered an error while searching: {e}", mention_author=False)
            return True # Stop further processing

        if not search_result or not search_result.get("results"):
            logger.info("Tavily search returned no results.")
            return None # Let the bot respond normally that it found nothing

        # Format the results for the LLM
        formatted_results = self.format_results(search_result)
        logger.info("Injecting search results into LLM context.")
        return 'append', [formatted_results]

    def format_results(self, search_result: Dict[str, Any]) -> str:
        """
        Formats the search results into a clean string for context injection.
        """
        snippets = []
        for result in search_result.get("results", []):
            snippet = f"- **{result.get('title', 'No Title')}** ([Source]({result.get('url', '#')}))\n" \
                      f"  - Content: {result.get('content', 'No content available.')}"
            snippets.append(snippet)
        
        if not snippets:
            return "No information found from the web search."

        return "Web Search Results (for your reference):\n" + "\n".join(snippets)
