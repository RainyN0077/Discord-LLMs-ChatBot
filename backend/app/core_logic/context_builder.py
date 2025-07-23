# backend/app/core_logic/context_builder.py
import json
import re
from typing import Dict, Any, List, Optional, Tuple
import discord

from .persona_manager import get_highest_configured_role, get_rich_identity
from ..utils import escape_content
from .knowledge_manager import knowledge_manager

# --- Constants for structured prompts ---
# Using constants makes the code cleaner, easier to read, and simplifies future modifications.
MESSAGE_FORMAT_TPL = "{author_id}: {content}{image_note}"
IMAGE_NOTE_TPL = " [该消息还包含{count}张图片]"
REPLY_CONTEXT_TPL = "[上下文：用户正在回复来自{author_info}的消息]\n回复的消息内容：{replied_content}"
DELETED_REPLY_CONTEXT_TPL = "[上下文：用户正在回复一条已被删除的消息。]"
DIRECT_MESSAGE_TPL = "{user_message}"
# [SECURITY] Use XML-like tags to wrap externally injected content to mitigate prompt injection.
TOOL_CONTEXT_TPL = "[来自工具的额外上下文]\n<tool_output>\n{data}\n</tool_output>"
MEMORY_CONTEXT_TPL = "[长期记忆]\n<knowledge>\n{data}\n</knowledge>"
WORLDBOOK_CONTEXT_TPL = "[相关世界设定]\n<knowledge>\n{data}\n</knowledge>"
USER_REQUEST_BLOCK_TPL = "[用户请求块]\n\n{parts}\n\n[/用户请求块]"


async def build_context_history(client: discord.Client, bot_config: Dict[str, Any], message: discord.Message, cutoff_timestamp: Optional[int]) -> Tuple[List[discord.Message], List[Dict[str, str]]]:
    """根据配置的上下文模式，构建历史消息列表和用于LLM的格式化历史。"""
    history_messages, history_for_llm = [], []
    context_mode = bot_config.get('context_mode', 'none')

    if context_mode == 'none':
        return [], []

    settings = bot_config.get(f'{context_mode}_context_settings', {})
    msg_limit = settings.get('message_limit', 10)
    char_limit = settings.get('char_limit', 4000)

    if msg_limit <= 0:
        return [], []

    fetched_history = []
    if context_mode == 'channel':
        # 限制历史记录获取数量以避免性能问题
        fetched_history = [msg async for msg in message.channel.history(limit=min(msg_limit * 2, 100), before=message, after=cutoff_timestamp)]
    elif context_mode == 'memory':
        trigger_keywords = bot_config.get("trigger_keywords", [])
        potential_history = [msg async for msg in message.channel.history(limit=max(msg_limit * 3, 50), before=message, after=cutoff_timestamp)]
        relevant_messages, processed_ids = [], set()
        for hist_msg in potential_history:
            if len(relevant_messages) >= msg_limit:
                break
            if hist_msg.id in processed_ids:
                continue

            is_bot_msg = hist_msg.author == client.user
            mentions_bot = client.user in hist_msg.mentions
            
            # --- [核心修复] ---
            # 检查被回复消息是否有效且未被删除
            replies_to_bot = False
            if hist_msg.reference and hist_msg.reference.resolved:
                # 需要显式检查解析消息的类型
                # 如果是DeletedReferencedMessage，就没有'author'属性
                if isinstance(hist_msg.reference.resolved, discord.Message):
                    replies_to_bot = hist_msg.reference.resolved.author == client.user
            # --- [修复结束] ---
            
            has_keyword = any(k.lower() in hist_msg.content.lower() for k in trigger_keywords)

            if is_bot_msg or mentions_bot or replies_to_bot or has_keyword:
                relevant_messages.append(hist_msg)
                processed_ids.add(hist_msg.id)
                if hist_msg.reference and isinstance(hist_msg.reference.resolved, discord.Message):
                    replied_to_msg = hist_msg.reference.resolved
                    if replied_to_msg.id not in processed_ids:
                        relevant_messages.append(replied_to_msg)
                        processed_ids.add(replied_to_msg.id)
        fetched_history = relevant_messages

    if not fetched_history:
        return [], []
    
    # 为LLM格式化历史记录
    fetched_history.sort(key=lambda m: m.created_at)
    user_personas = bot_config.get("user_personas", {})
    role_based_configs = bot_config.get("role_based_config", {})
    temp_history = []
    total_chars = 0

    for hist_msg in reversed(fetched_history):
        # 忽略没有内容的消息
        if not hist_msg.clean_content and not hist_msg.attachments:
            continue

        is_bot = hist_msg.author == client.user
        role = "assistant" if is_bot else "user"
        
        hist_role_config = None
        if not is_bot:
            hist_member = hist_msg.author
            if isinstance(hist_member, discord.User) and message.guild:
                hist_member = message.guild.get_member(hist_member.id) or hist_member
            
            if isinstance(hist_member, discord.Member):
                _, hist_role_config = get_highest_configured_role(hist_member, role_based_configs) or (None, None)
        
        # 对用户和机器人统一调用 get_rich_identity, role_config 对于机器人为 None
        rich_id = get_rich_identity(hist_msg.author, user_personas, hist_role_config)
        
        image_note = ""
        if hist_msg.attachments:
            image_count = len([att for att in hist_msg.attachments if att.content_type and att.content_type.startswith('image/')])
            if image_count > 0:
                image_note = IMAGE_NOTE_TPL.format(count=image_count)

        clean_content = escape_content(hist_msg.clean_content)

        if is_bot:
            # For bot messages, use content directly to avoid prefix imitation.
            content = f"{clean_content}{image_note}".strip()
        else:
            # For user messages, keep the original format with author ID.
            content = MESSAGE_FORMAT_TPL.format(
                author_id=rich_id,
                content=clean_content,
                image_note=image_note
            )

        if total_chars + len(content) > char_limit:
            break
        total_chars += len(content)
        temp_history.append({"role": role, "content": content})
    
    history_for_llm = list(reversed(temp_history))
    return fetched_history, history_for_llm

def format_user_message_for_llm(message: discord.Message, client: discord.Client, bot_config: Dict[str, Any], role_config: Optional[Dict[str, Any]], injected_data: Optional[str] = None) -> str:
    """将用户的当前消息格式化为最终LLM输入块。"""
    user_personas = bot_config.get("user_personas", {})
    role_based_configs = bot_config.get("role_based_config", {})
    
    # 替换消息中的@提及
    processed_content = message.content
    for mentioned_user in message.mentions:
        if mentioned_user.id != client.user.id and message.guild and (member := message.guild.get_member(mentioned_user.id)):
            _, m_role_config = get_highest_configured_role(member, role_based_configs) or (None, None)
            rich_id_str = get_rich_identity(member, user_personas, m_role_config)
            processed_content = processed_content.replace(f'<@{mentioned_user.id}>', rich_id_str).replace(f'<@!{mentioned_user.id}>', rich_id_str)
    final_text_content = processed_content.replace(f'<@{client.user.id}>', '').replace(f'<@!{client.user.id}>', '').strip()

    # [NEW] Remove custom emoji text, as they are now sent as images.
    final_text_content = re.sub(r'<a?:\w+:\d+>', '', final_text_content).strip()

    request_block_parts = []
    
    # 处理回复上下文 - 优雅处理已删除消息
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        replied_msg = message.reference.resolved
        replied_member = replied_msg.author
        if isinstance(replied_member, discord.User) and message.guild:
            replied_member = message.guild.get_member(replied_member.id) or replied_member
        
        replied_role_config = None
        if isinstance(replied_member, discord.Member):
            _, replied_role_config = get_highest_configured_role(replied_member, role_based_configs) or (None, None)
            
        replied_author_info = get_rich_identity(replied_msg.author, user_personas, replied_role_config)
        
        replied_text_content = escape_content(replied_msg.clean_content)
        final_replied_description = replied_text_content
        
        if replied_msg.attachments:
            image_count = len([att for att in replied_msg.attachments 
                              if att.content_type and att.content_type.startswith('image/')])
            
            if image_count > 0:
                if replied_text_content:
                    final_replied_description += f" (该消息还包含{image_count}张图片，请查看附件)"
                else:
                    final_replied_description = f"[消息内容是{image_count}张图片，请查看附件]"
        
        request_block_parts.append(REPLY_CONTEXT_TPL.format(author_info=replied_author_info, replied_content=final_replied_description))
    elif message.reference: # 如果引用存在但不是有效消息（即已被删除）
        request_block_parts.append(DELETED_REPLY_CONTEXT_TPL)

    # 添加当前消息中图片的信息
    current_image_info = ""
    if message.attachments:
        current_image_count = len([att for att in message.attachments
                                  if att.content_type and att.content_type.startswith('image/')])
        if current_image_count > 0:
            current_image_info = IMAGE_NOTE_TPL.format(count=current_image_count)

    author_rich_id = get_rich_identity(message.author, user_personas, role_config)
    
    current_user_message_str = MESSAGE_FORMAT_TPL.format(
        author_id=author_rich_id,
        content=escape_content(final_text_content),
        image_note=current_image_info
    )
    request_block_parts.append(current_user_message_str)
    
    # 处理插件注入的数据
    if injected_data:
        request_block_parts.append(TOOL_CONTEXT_TPL.format(data=injected_data))

    # --- New: Inject knowledge base content ---
    # 1. Inject World Book entries
    triggered_wb_entries = knowledge_manager.find_world_book_entries_for_text(final_text_content)
    if triggered_wb_entries:
        wb_content = "\n".join([f"- {entry['content']} (Keywords: {entry['keywords']})" for entry in triggered_wb_entries])
        request_block_parts.append(WORLDBOOK_CONTEXT_TPL.format(data=wb_content))

    # --- End of new section ---

    return USER_REQUEST_BLOCK_TPL.format(parts="\n\n".join(request_block_parts))

