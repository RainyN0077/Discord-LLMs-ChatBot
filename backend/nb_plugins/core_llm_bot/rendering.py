from typing import Any, Dict, Optional, Tuple
from typing import AsyncGenerator

from nonebot.adapters.discord import Bot, MessageEvent

from app.ports.bot_runtime import MessageSender
from app.utils import split_message


async def render_streaming_response(
    runtime: MessageSender,
    channel_id: str,
    response_generator: AsyncGenerator[Tuple[str, Any], None],
    reply_to_message_id: Optional[str] = None,
) -> Tuple[str, Optional[Dict[str, int]]]:
    """Render LLM streaming response via MessageSender interface.

    Args:
        runtime: MessageSender interface for sending messages.
        channel_id: Target channel ID.
        response_generator: Async generator yielding (response_type, data) tuples.
        reply_to_message_id: Optional message ID to reply to.

    Returns:
        Tuple of (full_response_text, usage_data_or_None).
    """
    sent_msg_id = None
    full_response = ""
    usage_data = None
    last_sent = ""

    async for response_type, data in response_generator:
        if response_type == "partial":
            content_chunks = split_message(data, 2000)
            current_chunk = content_chunks[0] if content_chunks else ""
            if sent_msg_id is None and current_chunk.strip():
                sent_msg_id = await runtime.send_message(
                    channel_id=channel_id,
                    content=current_chunk,
                    reply_to_message_id=reply_to_message_id,
                )
                last_sent = current_chunk
            elif sent_msg_id and current_chunk and current_chunk != last_sent:
                try:
                    await runtime.edit_message(
                        channel_id=channel_id,
                        message_id=sent_msg_id,
                        content=current_chunk,
                    )
                    last_sent = current_chunk
                except Exception:
                    pass
        elif response_type == "final":
            full_response = str(data or "")
        elif response_type == "usage":
            usage_data = data

    return full_response, usage_data


async def _render_streaming_response_old(
    bot: Bot,
    event: MessageEvent,
    response_generator: AsyncGenerator[Tuple[str, Any], None],
) -> Tuple[str, Optional[Dict[str, int]]]:
    """Old signature: uses bot.send / bot.edit_message directly.

    Kept for backward compatibility when USE_NEW_MAIN_PIPELINE is disabled.
    """
    sent_msg_id = None
    full_response = ""
    usage_data = None
    last_sent = ""

    async for response_type, data in response_generator:
        if response_type == "partial":
            content_chunks = split_message(data, 2000)
            current_chunk = content_chunks[0] if content_chunks else ""
            if sent_msg_id is None and current_chunk.strip():
                sent = await bot.send(event, current_chunk, reply_message=True)
                sent_msg_id = sent.id
                last_sent = current_chunk
            elif sent_msg_id and current_chunk and current_chunk != last_sent:
                try:
                    await bot.edit_message(
                        channel_id=event.channel_id,
                        message_id=sent_msg_id,
                        content=current_chunk,
                    )
                    last_sent = current_chunk
                except Exception:
                    pass
        elif response_type == "final":
            full_response = str(data or "")
        elif response_type == "usage":
            usage_data = data

    return full_response, usage_data
