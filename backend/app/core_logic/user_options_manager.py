from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResolvedUserOption:
    mode: str = "none"
    blacklist_mode: Optional[str] = None
    negative_portrait: Optional[str] = None
    whitelist_behavior: Optional[str] = None
    is_blocked: bool = False




def _user_in_rule(rule: Dict[str, Any], user_id: str) -> bool:
    users = rule.get("users") or {}
    user_id_str = str(user_id)
    for user_entry in users.values():
        if isinstance(user_entry, dict) and str(user_entry.get("user_id")) == user_id_str:
            return True
    return False


def _get_user_entry(rule: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    users = rule.get("users") or {}
    user_id_str = str(user_id)
    for user_entry in users.values():
        if isinstance(user_entry, dict) and str(user_entry.get("user_id")) == user_id_str:
            return user_entry
    return {}


def _match_rule(
    rules: Dict[str, Any],
    user_id: str,
    guild_id: Optional[str],
    channel_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    user_id_str = str(user_id)

    channel_rule = None
    guild_rule = None
    global_rule = None
    dm_rule = None

    for _rule_key, rule in rules.items():
        if not isinstance(rule, dict):
            continue
        scope_type = rule.get("scope_type", "")
        scope_id = str(rule.get("scope_id", ""))
        if scope_type == "channel" and scope_id == channel_id:
            channel_rule = rule
        elif scope_type == "guild" and scope_id == guild_id:
            guild_rule = rule
        elif scope_type == "global" or (not scope_id and scope_type != "dm"):
            global_rule = rule
        elif scope_type == "dm" and scope_id == channel_id:
            dm_rule = rule

    for candidate, label in [(channel_rule, "channel"), (guild_rule, "guild"), (global_rule, "global"), (dm_rule, "dm")]:
        if candidate and _user_in_rule(candidate, user_id_str):
            logger.info(f"[uo:match] MATCHED user={user_id_str} scope={label} mode={candidate.get('mode')}")
            return candidate

    return None


def resolve_user_options(
    config: dict,
    guild_id: Optional[str],
    channel_id: str,
    user_id: str,
) -> ResolvedUserOption:
    user_options = config.get("user_options") or {}
    if not user_options.get("enabled"):
        return ResolvedUserOption()

    resolved = ResolvedUserOption()
    rules: Dict[str, Any] = user_options.get("rules") or {}
    if not rules:
        return resolved

    rule = _match_rule(rules, user_id, guild_id, channel_id)
    if not rule:
        return resolved

    resolved.mode = rule.get("mode", "blacklist")
    resolved.is_blocked = True

    user_entry = _get_user_entry(rule, user_id)
    if resolved.mode == "blacklist":
        resolved.blacklist_mode = (user_entry.get("blacklist_mode") or "deny_response")
        resolved.negative_portrait = user_entry.get("negative_portrait") or ""
    elif resolved.mode == "whitelist":
        resolved.whitelist_behavior = rule.get("whitelist_behavior", "triggers_only")

    return resolved


def is_user_blocked_from_response(
    config: dict,
    guild_id: Optional[str],
    channel_id: str,
    user_id: str,
) -> bool:
    resolved = resolve_user_options(config, guild_id, channel_id, user_id)
    if not resolved.is_blocked:
        return False
    logger.info(
        f"[uo:gate:check] user={user_id} mode={resolved.mode} "
        f"blacklist_mode={resolved.blacklist_mode} whitelist_behavior={resolved.whitelist_behavior} "
        f"is_blocked={resolved.is_blocked}"
    )
    if resolved.mode == "blacklist":
        block = resolved.blacklist_mode in ("deny_response", "block_messages")
        logger.info(f"[uo:gate:result] user={user_id} blacklist_mode={resolved.blacklist_mode} => block={block}")
        return block
    if resolved.mode == "whitelist":
        block = resolved.whitelist_behavior == "triggers_only"
        logger.info(f"[uo:gate:result] user={user_id} whitelist_behavior={resolved.whitelist_behavior} => block={block}")
        return block
    logger.info(f"[uo:gate:result] user={user_id} unknown mode={resolved.mode} => block=False")
    return False


def is_user_blocked_from_context(
    config: dict,
    guild_id: Optional[str],
    channel_id: str,
    user_id: str,
) -> bool:
    resolved = resolve_user_options(config, guild_id, channel_id, user_id)
    if not resolved.is_blocked:
        return False
    if resolved.mode == "blacklist":
        return resolved.blacklist_mode == "block_messages"
    return False


def get_negative_portrait(
    config: dict,
    guild_id: Optional[str],
    channel_id: str,
    user_id: str,
) -> Optional[str]:
    resolved = resolve_user_options(config, guild_id, channel_id, user_id)
    if resolved.blacklist_mode == "negative_portrait" and resolved.negative_portrait:
        return resolved.negative_portrait
    return None


def is_user_whitelisted_for_context(
    config: dict,
    guild_id: Optional[str],
    channel_id: str,
    user_id: str,
) -> bool:
    user_options = config.get("user_options") or {}
    if not user_options.get("enabled"):
        return True

    rules: Dict[str, Any] = user_options.get("rules") or {}
    if not rules:
        return True

    user_id_str = str(user_id)
    channel_rule = None
    guild_rule = None
    global_rule = None

    for _rule_key, rule in rules.items():
        if not isinstance(rule, dict):
            continue
        scope_type = rule.get("scope_type", "")
        scope_id = str(rule.get("scope_id", ""))
        if scope_type == "channel" and scope_id == channel_id:
            channel_rule = rule
        elif scope_type == "guild" and scope_id == guild_id:
            guild_rule = rule
        elif scope_type == "global" or (not scope_id and scope_type not in ("dm", "channel", "guild")):
            global_rule = rule

    for rule in [channel_rule, guild_rule, global_rule]:
        if rule and rule.get("mode") == "whitelist" and rule.get("whitelist_behavior") == "messages_only":
            return _user_in_rule(rule, user_id_str)

    return True


def should_filter_history(
    config: dict,
    guild_id: Optional[str],
    channel_id: str,
) -> bool:
    user_options = config.get("user_options") or {}
    if not user_options.get("enabled"):
        return False

    rules: Dict[str, Any] = user_options.get("rules") or {}
    channel_rule = None
    guild_rule = None
    global_rule = None

    for _rule_key, rule in rules.items():
        if not isinstance(rule, dict):
            continue
        scope_type = rule.get("scope_type", "")
        scope_id = str(rule.get("scope_id", ""))
        if scope_type == "channel" and scope_id == channel_id:
            channel_rule = rule
        elif scope_type == "guild" and scope_id == guild_id:
            guild_rule = rule
        elif scope_type == "global" or (not scope_id and scope_type not in ("dm", "channel", "guild")):
            global_rule = rule

    for rule in [channel_rule, guild_rule, global_rule]:
        if not rule:
            continue
        mode = rule.get("mode")
        if mode == "whitelist" and rule.get("whitelist_behavior") == "messages_only":
            return True
        if mode == "blacklist":
            return True

    return False


def get_formatted_block_notice(
    author: Any,
    user_personas: dict,
    role_configs: dict,
    block_mode: str,
) -> str:
    from .persona_manager import get_rich_identity, _format_author_id

    rich_id = get_rich_identity(author, user_personas, None)
    author_str = _format_author_id(author, rich_id)

    if block_mode == "block_messages":
        return f"{author_str} 用户已被拉黑"
    elif block_mode == "deny_response":
        return f"[用户已被拉黑] {author_str}"
    return ""
