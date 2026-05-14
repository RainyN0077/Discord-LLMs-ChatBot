from typing import Any, Dict, List, Optional, Tuple

from app.handlers.context_assembler import build_full_context as _build_full_context
from .event_shim import MessageContext


async def build_full_context(
    bot,
    config: Dict[str, Any],
    message_ctx: MessageContext,
    memory_cutoffs: Dict[int, Any],
    injected_data: Optional[str] = None,
) -> Tuple[str, str, List[Dict[str, str]], List[MessageContext], Optional[str], Optional[Dict[str, Any]]]:
    return await _build_full_context(
        bot=bot,
        config=config,
        message=message_ctx,
        memory_cutoffs=memory_cutoffs,
        injected_data=injected_data,
    )
