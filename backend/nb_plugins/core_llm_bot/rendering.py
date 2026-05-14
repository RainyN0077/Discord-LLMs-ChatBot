from typing import Any, Dict, Optional, Tuple
from typing import AsyncGenerator

from nonebot.adapters.discord import Bot, MessageEvent

from app.utils import split_message


async def render_streaming_response(
    bot: Bot,
    event: MessageEvent,
    response_generator: AsyncGenerator[Tuple[str, Any], None],
) -> Tuple[str, Optional[Dict[str, int]]]:
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
