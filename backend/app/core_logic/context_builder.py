# backend/app/core_logic/context_builder.py
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, Any, List, Optional, Tuple

from .persona_manager import get_highest_configured_role, get_rich_identity, find_mentioned_users_by_keywords, _format_author_id
from .user_options_manager import is_user_blocked_from_context, is_user_whitelisted_for_context, should_filter_history, get_formatted_block_notice, resolve_user_options
from ..utils import escape_content, matches_trigger_keywords
from ..security.input_sanitizer import sanitize_user_input
from .knowledge_manager import get_knowledge_manager

logger = logging.getLogger(__name__)


def _get_bot_user_id(client: Any) -> int:
    user = getattr(client, 'user', None)
    if user is not None and hasattr(user, 'id') and not callable(user.id):
        return user.id
    if hasattr(client, 'self_info') and client.self_info is not None:
        return int(client.self_info.id)
    if hasattr(client, 'self_id'):
        return int(client.self_id)
    return 0


def _is_api_message(msg: Any) -> bool:
    cls_name = type(msg).__name__
    return cls_name == 'MessageGet'


def _safe_int(snowflake: Any) -> int:
    return int(str(snowflake))


class _ApiHistoryWrapper:
    __slots__ = ('_msg', '_bot_user_id', '_guild_id')

    def __init__(self, msg: Any, bot_user_id: int, guild_id: Optional[int]) -> None:
        self._msg = msg
        self._bot_user_id = bot_user_id
        self._guild_id = guild_id

    @property
    def id(self) -> int:
        return _safe_int(self._msg.id)

    @property
    def content(self) -> str:
        return getattr(self._msg, 'content', '') or ''

    @property
    def clean_content(self) -> str:
        return self.content

    @property
    def created_at(self):
        return getattr(self._msg, 'timestamp', None)

    @property
    def author(self) -> '_ApiUserWrapper':
        return _ApiUserWrapper(getattr(self._msg, 'author', None), self._bot_user_id)

    @property
    def mentions(self):
        return [_ApiUserWrapper(u, self._bot_user_id) for u in getattr(self._msg, 'mentions', []) or []]

    @property
    def attachments(self):
        return [_ApiAttachmentWrapper(a) for a in getattr(self._msg, 'attachments', []) or []]

    @property
    def reference(self) -> Optional['_ApiReferenceWrapper']:
        ref = getattr(self._msg, 'referenced_message', None)
        if ref is None:
            return None
        return _ApiReferenceWrapper(ref, self._bot_user_id, self._guild_id)

    @property
    def guild(self) -> Any:
        return None


class _ApiUserWrapper:
    __slots__ = ('_user', '_bot_user_id')

    def __init__(self, user: Any, bot_user_id: int) -> None:
        self._user = user
        self._bot_user_id = bot_user_id

    @property
    def id(self) -> int:
        return _safe_int(self._user.id) if self._user else 0

    @property
    def display_name(self) -> str:
        if self._user is None:
            return 'Unknown'
        return getattr(self._user, 'global_name', None) or getattr(self._user, 'username', 'Unknown')

    @property
    def username(self) -> str:
        if self._user is None:
            return 'Unknown'
        return getattr(self._user, 'username', 'Unknown')

    @property
    def name(self) -> str:
        return self.username

    @property
    def bot(self) -> bool:
        if self._user is None:
            return False
        bot_val = getattr(self._user, 'bot', False)
        if bot_val is True:
            return True
        return self.id == self._bot_user_id

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _ApiUserWrapper):
            return self.id == other.id
        if hasattr(other, 'id'):
            return self.id == _safe_int(other.id)
        if hasattr(other, 'self_info'):
            return self.id == _safe_int(other.self_info.id)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)


class _ApiAttachmentWrapper:
    __slots__ = ('_att',)

    def __init__(self, att: Any) -> None:
        self._att = att

    @property
    def content_type(self) -> str:
        return getattr(self._att, 'content_type', '') or ''


class _ApiReferenceWrapper:
    __slots__ = ('_resolved',)

    def __init__(self, resolved_msg: Any, bot_user_id: int, guild_id: Optional[int]) -> None:
        self._resolved = _ApiHistoryWrapper(resolved_msg, bot_user_id, guild_id) if resolved_msg else None

    @property
    def resolved(self):
        return self._resolved


async def _fetch_history_via_api(client: Any, channel_id: int, message_id: int, limit: int, cutoff_timestamp: Optional[datetime]) -> List['_ApiHistoryWrapper']:
    if not hasattr(client, 'get_channel_messages'):
        return []
    max_retries = 2
    retry_delay = 1.0
    raw = None
    for attempt in range(max_retries + 1):
        try:
            raw = await client.get_channel_messages(
                channel_id=channel_id,
                before=str(message_id),
                limit=min(limit, 100),
            )
            break
        except Exception:
            if attempt < max_retries:
                logger.warning(
                    "Failed to fetch channel history via REST API for channel %s (attempt %d/%d), retrying in %.1fs...",
                    channel_id, attempt + 1, max_retries + 1, retry_delay
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.warning("Failed to fetch channel history via REST API for channel %s after %d attempts", channel_id, max_retries + 1, exc_info=True)
                return []
    if raw is None:
        return []
    bot_user_id = _get_bot_user_id(client)
    guild_id = None
    results = []
    for msg in raw:
        if _is_api_message(msg):
            ts = getattr(msg, 'timestamp', None)
            if cutoff_timestamp is not None and ts is not None and ts < cutoff_timestamp:
                continue
            results.append(_ApiHistoryWrapper(msg, bot_user_id, guild_id))
    return results

# --- Constants for structured prompts ---
# Using constants makes the code cleaner, easier to read, and simplifies future modifications.
MESSAGE_FORMAT_TPL = "{author_id}: {content}{image_note}"
USER_MESSAGE_TPL = "[{author_id_str}]: {content}{image_note}"
BOT_MESSAGE_TPL = "[{author_id_str}]: {content}{image_note}"
OWN_MESSAGE_TPL = "{content}{image_note}"
IMAGE_NOTE_TPL = " [该消息还包含{count}张图片]"
REPLY_CONTEXT_TPL = "[上下文：用户正在回复来自{author_info}的消息]\n回复的消息内容：{replied_content}"
DELETED_REPLY_CONTEXT_TPL = "[上下文：用户正在回复一条已被删除的消息。]"
INACCESSIBLE_REPLY_CONTEXT_TPL = "[上下文：用户正在回复一条当前不可见的消息，可能是图片、嵌入式内容或被网关忽略的消息。]"
DIRECT_MESSAGE_TPL = "{user_message}"
# [SECURITY] Use XML-like tags to wrap externally injected content to mitigate prompt injection.
TOOL_CONTEXT_TPL = "[来自工具的额外上下文]\n<tool_output>\n{data}\n</tool_output>"
MEMORY_CONTEXT_TPL = "[长期记忆]\n<knowledge>\n{data}\n</knowledge>"
WORLDBOOK_CONTEXT_TPL = "[相关世界设定]\n<knowledge>\n{data}\n</knowledge>"
USER_REQUEST_BLOCK_TPL = "[用户请求块]\n\n{parts}\n\n[/用户请求块]"
DEFAULT_WORLDBOOK_MAX_ENTRIES = 20
DEFAULT_WORLDBOOK_CHAR_LIMIT = 3000

# --- Prompt template overrides ---
# 键名与 prompts.py DEFAULT_TEMPLATES 的 14 键一致；templates 参数由调用方
# 从 bot_config['prompt_templates'] 归一化传入（运行时与 preview 均生效），
# 未配置时恒用下方模块常量，行为与旧版逐字节一致。


def _resolve_tpl(
    templates: Optional[Dict[str, Any]], key: str, default: str
) -> str:
    """返回自定义模板覆盖值；未提供/空串/非字符串时回退模块默认常量."""
    if templates is None:
        return default
    value = templates.get(key)
    if isinstance(value, str) and value:
        return value
    return default


def _format_tpl(template: str, default: str, **kwargs) -> str:
    """安全格式化模板：占位符缺失等异常时回退默认常量，避免预览崩溃."""
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return default.format(**kwargs)


def resolve_prompt_templates(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 bot_config 读取 ``prompt_templates`` 并归一化：非 dict（含缺省 None）一律返回 None.

    所有消费点只接收 ``None`` 或 ``dict``，键值非法由 ``_resolve_tpl``/``_format_tpl``
    回退默认常量，保证"未配置模板 = 旧行为逐字节不变"。
    """
    templates = config.get("prompt_templates")
    if isinstance(templates, dict):
        return templates
    return None


def format_memory_context(
    templates: Optional[Dict[str, Any]], memory_block: str
) -> Optional[str]:
    """用 ``memory_context`` 模板键格式化长期记忆块；不适用时返回 None（调用方回退旧拼接）.

    仅当模板键存在、为合法非空字符串、且包含 ``{data}`` 占位符且格式化无异常时生效；
    键缺失/非字符串/空串/无占位符/占位符不匹配/格式化异常一律返回 ``None``，
    由调用方保持原有 f-string 拼接（逐字节不变）。
    """
    if templates is None:
        return None
    value = templates.get("memory_context")
    if not isinstance(value, str) or not value:
        return None
    if "{data}" not in value:
        return None
    try:
        return value.format(data=memory_block)
    except (KeyError, IndexError, ValueError):
        return None


async def build_context_history(client: Any, bot_config: Dict[str, Any], message: Any, cutoff_timestamp: Optional[datetime]) -> Tuple[List[Any], List[Dict[str, str]]]:
    history_messages, history_for_llm = [], []
    context_mode = bot_config.get('context_mode', 'none')
    if context_mode == 'none':
        return [], []

    settings = bot_config.get(f'{context_mode}_context_settings', {})
    msg_limit = settings.get('message_limit', 10)
    char_limit = settings.get('char_limit', 4000)
    unlimited_context_length = bool(settings.get('unlimited_context_length', False))
    unlimited_message_count = bool(settings.get('unlimited_message_count', False))
    if not unlimited_message_count and msg_limit <= 0:
        return [], []

    bot_user_id = _get_bot_user_id(client)

    guild_id = str(message.guild.id) if message.guild else None
    channel_id = str(message.channel.id)

    use_api_history = not hasattr(message.channel, 'history')
    if use_api_history:
        raw_limit = None if unlimited_message_count else max(msg_limit * 3, 50)
        fetched_history: List[Any] = await _fetch_history_via_api(
            client, message.channel.id, message.id, raw_limit or 100, cutoff_timestamp)
    else:
        channel = message.channel
        before_obj = SimpleNamespace(id=message.id)
        raw_limit = None if unlimited_message_count else max(msg_limit * 3, 100)
        if context_mode == 'channel':
            raw_limit = None if unlimited_message_count else min(msg_limit * 2, 100)
        fetched_history = [msg async for msg in channel.history(limit=raw_limit, before=before_obj, after=cutoff_timestamp)]

    if context_mode == 'memory':
        trigger_keywords = bot_config.get("trigger_keywords", [])
        trigger_match_mode = bot_config.get("trigger_match_mode", "contains")
        trigger_case_sensitive = bool(bot_config.get("trigger_case_sensitive", False))
        relevant_messages, processed_ids = [], set()
        for hist_msg in fetched_history:
            if not unlimited_message_count and len(relevant_messages) >= msg_limit:
                break
            if hist_msg.id in processed_ids:
                continue

            is_bot_msg = _is_message_from_bot(hist_msg, bot_user_id)
            mentions_bot = _mentions_bot(hist_msg, bot_user_id)
            replies_to_bot = _replies_to_bot(hist_msg, bot_user_id)

            has_keyword = matches_trigger_keywords(
                hist_msg.content,
                trigger_keywords,
                match_mode=trigger_match_mode,
                case_sensitive=trigger_case_sensitive
            )

            if is_bot_msg or mentions_bot or replies_to_bot or has_keyword:
                relevant_messages.append(hist_msg)
                processed_ids.add(hist_msg.id)
                ref = getattr(hist_msg, 'reference', None)
                if ref is not None:
                    resolved = getattr(ref, 'resolved', None)
                    if resolved is not None and type(resolved).__name__ != 'DeletedReferencedMessage':
                        if resolved.id not in processed_ids:
                            relevant_messages.append(resolved)
                            processed_ids.add(resolved.id)
        fetched_history = relevant_messages

    if not fetched_history:
        return [], []

    fetched_history.sort(key=lambda m: m.created_at if m.created_at else datetime.min.replace(tzinfo=timezone.utc))
    user_personas = bot_config.get("user_personas", {})
    role_based_configs = bot_config.get("role_based_config", {})
    temp_history = []
    total_chars = 0

    for hist_msg in reversed(fetched_history):
        if not hist_msg.clean_content and not hist_msg.attachments:
            continue

        if should_filter_history(bot_config, guild_id, channel_id):
            hist_author_id = str(hist_msg.author.id)
            if is_user_blocked_from_context(bot_config, guild_id, channel_id, hist_author_id):
                continue
            if not is_user_whitelisted_for_context(bot_config, guild_id, channel_id, hist_author_id):
                continue

        msg_class = _classify_message_author(hist_msg, bot_user_id)
        role = "assistant" if msg_class == 'own_bot' else "user"

        hist_role_config = None
        if msg_class == 'user':
            hist_member = hist_msg.author
            if not hasattr(hist_member, 'roles') and hasattr(message, 'guild') and message.guild and hasattr(message.guild, 'get_member'):
                hist_member = message.guild.get_member(hist_member.id) or hist_member
            if hasattr(hist_member, 'roles'):
                _, hist_role_config = get_highest_configured_role(hist_member, role_based_configs) or (None, None)

        rich_id = get_rich_identity(hist_msg.author, user_personas, hist_role_config)
        author_id_str = _format_author_id(hist_msg.author, rich_id)

        image_note = ""
        if hist_msg.attachments:
            image_count = len([att for att in hist_msg.attachments if att.content_type and att.content_type.startswith('image/')])
            if image_count > 0:
                image_note = IMAGE_NOTE_TPL.format(count=image_count)

        clean_content = escape_content(hist_msg.clean_content)

        if msg_class == 'own_bot':
            content = OWN_MESSAGE_TPL.format(content=clean_content, image_note=image_note).strip()
        elif msg_class == 'other_bot':
            content = BOT_MESSAGE_TPL.format(
                author_id_str=author_id_str,
                content=clean_content,
                image_note=image_note
            )
        else:
            content = USER_MESSAGE_TPL.format(
                author_id_str=author_id_str,
                content=clean_content,
                image_note=image_note
            )

        if not unlimited_context_length and total_chars + len(content) > char_limit:
            break
        total_chars += len(content)
        temp_history.append({"role": role, "content": content})

    history_for_llm = list(reversed(temp_history))
    return fetched_history, history_for_llm


def _is_message_from_bot(hist_msg: Any, bot_user_id: int) -> bool:
    return hist_msg.author.id == bot_user_id


def _classify_message_author(hist_msg: Any, bot_user_id: int) -> str:
    """Returns 'own_bot', 'other_bot', or 'user'."""
    if hist_msg.author.id == bot_user_id:
        return 'own_bot'
    if getattr(hist_msg.author, 'bot', False):
        return 'other_bot'
    return 'user'


def _mentions_bot(hist_msg: Any, bot_user_id: int) -> bool:
    mentions = getattr(hist_msg, 'mentions', None)
    if not mentions:
        return False
    return any(u.id == bot_user_id for u in mentions)


def _replies_to_bot(hist_msg: Any, bot_user_id: int) -> bool:
    ref = getattr(hist_msg, 'reference', None)
    if ref is None:
        return False
    resolved = getattr(ref, 'resolved', None)
    if resolved is None:
        return False
    return getattr(resolved.author, 'id', None) == bot_user_id

async def format_user_message_for_llm(
    message: Any,
    client: Any,
    bot_config: Dict[str, Any],
    role_config: Optional[Dict[str, Any]],
    injected_data: Optional[str] = None,
    world_book_entries: Optional[List[Dict[str, Any]]] = None,
    templates: Optional[Dict[str, Any]] = None,
) -> str:
    """将用户的当前消息格式化为最终LLM输入块。

    ``templates`` 由调用方（运行时 pipeline / 路由 / preview）从
    ``bot_config['prompt_templates']`` 归一化后传入，键名与 prompts.py
    DEFAULT_TEMPLATES 一致；未配置（None）时恒用模块默认常量。
    """
    # Resolve template overrides once (None → module defaults).
    user_message_tpl = _resolve_tpl(templates, "message_format", USER_MESSAGE_TPL)
    image_note_tpl = _resolve_tpl(templates, "image_note", IMAGE_NOTE_TPL)
    reply_context_tpl = _resolve_tpl(templates, "reply_context", REPLY_CONTEXT_TPL)
    deleted_reply_tpl = _resolve_tpl(templates, "deleted_reply_context", DELETED_REPLY_CONTEXT_TPL)
    tool_context_tpl = _resolve_tpl(templates, "tool_context", TOOL_CONTEXT_TPL)
    worldbook_context_tpl = _resolve_tpl(templates, "worldbook_context", WORLDBOOK_CONTEXT_TPL)
    user_request_block_tpl = _resolve_tpl(templates, "user_request_block", USER_REQUEST_BLOCK_TPL)

    user_personas = bot_config.get("user_personas", {})
    role_based_configs = bot_config.get("role_based_config", {})
    
    # 保留用户 mention token（<@id>），仅移除对机器人的 mention token。
    # 这样模型在回复时可以复用正确的 Discord @ 语法。
    bot_user_id = _get_bot_user_id(client)
    final_text_content = message.content.replace(f'<@{bot_user_id}>', '').replace(f'<@!{bot_user_id}>', '').strip()

    # [NEW] Remove custom emoji text, as they are now sent as images.
    final_text_content = re.sub(r'<a?:\w+:\d+>', '', final_text_content).strip()

    # [SECURITY] Sanitize user input to filter prompt injection patterns.
    final_text_content = sanitize_user_input(final_text_content)

    request_block_parts = []
    
    # 处理回复上下文 - 优雅处理已删除消息
    if message.reference and hasattr(message.reference.resolved, 'clean_content'):
        replied_msg = message.reference.resolved
        replied_member = replied_msg.author
        if not hasattr(replied_member, 'roles') and hasattr(message, 'guild') and message.guild and hasattr(message.guild, 'get_member'):
            replied_member = message.guild.get_member(replied_member.id) or replied_member
        
        replied_role_config = None
        if hasattr(replied_member, 'roles'):
            _, replied_role_config = get_highest_configured_role(replied_member, role_based_configs) or (None, None)

        replied_rich_id = get_rich_identity(replied_msg.author, user_personas, replied_role_config)
        replied_author_info = _format_author_id(replied_msg.author, replied_rich_id)
        
        replied_text_content = escape_content(replied_msg.clean_content)
        # [SECURITY] Sanitize replied message content to filter prompt injection patterns.
        replied_text_content = sanitize_user_input(replied_text_content)
        final_replied_description = replied_text_content
        
        if replied_msg.attachments:
            image_count = len([att for att in replied_msg.attachments 
                              if att.content_type and att.content_type.startswith('image/')])
            
            if image_count > 0:
                if replied_text_content:
                    final_replied_description += f" (该消息还包含{image_count}张图片，请查看附件)"
                else:
                    final_replied_description = f"[消息内容是{image_count}张图片，请查看附件]"
        
        request_block_parts.append(_format_tpl(
            reply_context_tpl, REPLY_CONTEXT_TPL,
            author_info=replied_author_info, replied_content=final_replied_description,
        ))
    elif message.reference:
        resolved = getattr(message.reference, 'resolved', None)
        if type(resolved).__name__ == 'DeletedReferencedMessage':
            request_block_parts.append(_format_tpl(deleted_reply_tpl, DELETED_REPLY_CONTEXT_TPL))
        else:
            request_block_parts.append(INACCESSIBLE_REPLY_CONTEXT_TPL)

    # 添加当前消息中图片的信息
    current_image_info = ""
    if message.attachments:
        current_image_count = len([att for att in message.attachments
                                  if att.content_type and att.content_type.startswith('image/')])
        if current_image_count > 0:
            current_image_info = _format_tpl(
                image_note_tpl, IMAGE_NOTE_TPL, count=current_image_count
            )

    author_rich_id = get_rich_identity(message.author, user_personas, role_config)
    author_id_str = _format_author_id(message.author, author_rich_id)

    guild_id = str(message.guild.id) if message.guild else None
    channel_id = str(message.channel.id)
    user_id_str = str(message.author.id)

    user_options_config = bot_config.get("user_options") or {}
    if user_options_config.get("enabled"):
        resolved = resolve_user_options(bot_config, guild_id, channel_id, user_id_str)
        if resolved.is_blocked and resolved.mode == "blacklist":
            block_notice = get_formatted_block_notice(
                message.author, user_personas, role_based_configs, resolved.blacklist_mode
            )
            if resolved.blacklist_mode == "block_messages":
                return _format_tpl(
                    user_request_block_tpl, USER_REQUEST_BLOCK_TPL, parts=block_notice
                )
            elif resolved.blacklist_mode == "deny_response":
                request_block_parts.insert(0, block_notice)

    user_identity_block = f"[当前用户信息]\n[{author_id_str}]\n[/当前用户信息]"
    request_block_parts.insert(0, user_identity_block)

    current_user_message_str = _format_tpl(
        user_message_tpl, USER_MESSAGE_TPL,
        author_id_str=author_id_str,
        content=escape_content(final_text_content),
        image_note=current_image_info,
    )
    request_block_parts.append(current_user_message_str)
    
    # 处理插件注入的数据
    if injected_data:
        request_block_parts.append(_format_tpl(tool_context_tpl, TOOL_CONTEXT_TPL, data=injected_data))

    # --- Inject world book content ---
    all_wb_entries = []
    added_entry_ids = set()

    if world_book_entries is not None:
        for entry in world_book_entries:
            if entry.get('id') not in added_entry_ids:
                all_wb_entries.append(entry)
                added_entry_ids.add(entry.get('id'))
    else:
        relevant_user_ids = {str(message.author.id)}
        for mentioned_user in message.mentions:
            relevant_user_ids.add(str(mentioned_user.id))

        keyword_mentioned_ids = find_mentioned_users_by_keywords(final_text_content, user_personas)
        relevant_user_ids.update(keyword_mentioned_ids)

        for user_id in relevant_user_ids:
            user_entries = await get_knowledge_manager().get_world_book_entries_for_user(user_id)
            for entry in user_entries:
                if entry['id'] not in added_entry_ids:
                    all_wb_entries.append(entry)
                    added_entry_ids.add(entry['id'])

        text_triggered_entries = await get_knowledge_manager().find_world_book_entries_for_text(final_text_content)
        for entry in text_triggered_entries:
            if entry['id'] not in added_entry_ids:
                all_wb_entries.append(entry)
                added_entry_ids.add(entry['id'])

    if all_wb_entries:
        max_entries = int(bot_config.get("world_book_context_max_entries", DEFAULT_WORLDBOOK_MAX_ENTRIES))
        char_limit = int(bot_config.get("world_book_context_char_limit", DEFAULT_WORLDBOOK_CHAR_LIMIT))
        if max_entries <= 0:
            max_entries = DEFAULT_WORLDBOOK_MAX_ENTRIES
        if char_limit <= 0:
            char_limit = DEFAULT_WORLDBOOK_CHAR_LIMIT

        lines = []
        total_chars = 0
        for entry in all_wb_entries[:max_entries]:
            line = f"- {entry['content']} (Keywords: {entry['keywords']})"
            if total_chars + len(line) > char_limit:
                break
            lines.append(line)
            total_chars += len(line)

        if lines:
            wb_content = "\n".join(lines)
            request_block_parts.append(_format_tpl(
                worldbook_context_tpl, WORLDBOOK_CONTEXT_TPL, data=wb_content
            ))

    # --- End of new section ---

    return _format_tpl(
        user_request_block_tpl, USER_REQUEST_BLOCK_TPL,
        parts="\n\n".join(request_block_parts),
    )

