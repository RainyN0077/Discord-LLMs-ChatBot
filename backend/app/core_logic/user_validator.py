import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def validate_user_id(user_id: str, guild: Any) -> Optional[Any]:
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        logger.debug("Invalid user_id format for validation: %s", user_id)
        return None
    try:
        member = guild.get_member(uid)
        if member is not None:
            return member
        member = await guild.fetch_member(uid)
        return member
    except Exception as e:
        logger.debug("User ID %s not found in guild: %s", user_id, e)
        return None


def resolve_user_identity(user_id: str, personas: Dict[str, Any], guild: Optional[Any] = None) -> str:
    persona_info = next((p for p in personas.values() if p.get("id") == user_id), None)
    if persona_info:
        nickname = persona_info.get("nickname")
        if nickname:
            return nickname
    if guild:
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return f"User({user_id})"
        member = guild.get_member(uid)
        if member:
            return member.display_name
    return f"User({user_id})"
