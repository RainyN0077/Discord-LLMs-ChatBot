from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ResolvedUserOption:
    mode: str = "none"
    blacklist_mode: Optional[str] = None
    negative_portrait: Optional[str] = None
    whitelist_behavior: Optional[str] = None
    is_blocked: bool = False


RULE_KEY_GLOBAL = "*"


def _make_key(scope_type: str, scope_id: str) -> str:
    if scope_type == "global" or not scope_id:
        return RULE_KEY_GLOBAL
    return f"{scope_type}:{scope_id}"


def _match_rule(
    rules: Dict[str, Any],
    user_id: str,
    guild_id: Optional[str],
    channel_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if channel_id:
        key = _make_key("channel", channel_id)
        rule = rules.get(key)
        if rule and str(user_id) in (rule.get("users") or {}):
            return rule

    if guild_id:
        key = _make_key("guild", guild_id)
        rule = rules.get(key)
        if rule and str(user_id) in (rule.get("users") or {}):
            return rule

    rule = rules.get(RULE_KEY_GLOBAL)
    if rule and str(user_id) in (rule.get("users") or {}):
        return rule

    if channel_id:
        key = _make_key("dm", channel_id)
        rule = rules.get(key)
        if rule and str(user_id) in (rule.get("users") or {}):
            return rule

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

    if resolved.mode == "blacklist":
        user_entry = (rule.get("users") or {}).get(str(user_id), {})
        resolved.blacklist_mode = user_entry.get("blacklist_mode", "deny_response")
        resolved.negative_portrait = user_entry.get("negative_portrait", "")
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
    if resolved.mode == "blacklist":
        return resolved.blacklist_mode in ("deny_response", "block_messages")
    if resolved.mode == "whitelist":
        return resolved.whitelist_behavior == "triggers_only"
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

    for key_priority in [
        _make_key("channel", channel_id),
        _make_key("guild", guild_id) if guild_id else None,
        RULE_KEY_GLOBAL,
    ]:
        if not key_priority:
            continue
        rule = rules.get(key_priority)
        if not rule:
            continue
        if rule.get("mode") == "whitelist" and rule.get("whitelist_behavior") == "messages_only":
            return str(user_id) in (rule.get("users") or {})

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
    for key_priority in [
        _make_key("channel", channel_id),
        _make_key("guild", guild_id) if guild_id else None,
        RULE_KEY_GLOBAL,
    ]:
        if not key_priority:
            continue
        rule = rules.get(key_priority)
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
