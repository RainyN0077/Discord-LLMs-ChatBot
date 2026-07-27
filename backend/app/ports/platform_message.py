"""平台无关消息模型 — 统一各平台消息格式.

替代 nb_plugins/core_llm_bot/event_shim.py 中的 MessageContext.
所有平台适配器必须将平台原生消息转换为此模型。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional


@dataclass
class AuthorInfo:
    """平台无关的作者信息."""

    id: str
    name: str
    display_name: str
    roles: List[str] = field(default_factory=list)

    @property
    def bot(self) -> bool:
        """返回是否为 Bot 账号."""
        return False

    def __hash__(self) -> int:
        return hash(self.id)

    def __bool__(self) -> bool:
        return True


@dataclass
class ChannelInfo:
    """平台无关的频道信息."""

    id: str
    name: str = ""
    type: str = "text"  # 'text', 'dm', 'voice', etc.


@dataclass
class GuildInfo:
    """平台无关的服务器/群组信息."""

    id: str
    name: str = ""


@dataclass
class AttachmentInfo:
    """平台无关的附件信息."""

    url: str
    filename: str = ""
    content_type: str = ""
    bytes: Optional[bytes] = None


@dataclass
class PlatformMessage:
    """平台无关的统一消息模型.

    替代 nb_plugins/core_llm_bot/event_shim.py 中的 MessageContext.
    所有平台适配器必须将平台原生消息转换为此模型。
    """

    id: str
    content: str
    author: AuthorInfo
    channel: ChannelInfo
    guild: Optional[GuildInfo] = None
    mentions: List[AuthorInfo] = field(default_factory=list)
    attachments: List[AttachmentInfo] = field(default_factory=list)
    reply_to: Optional["PlatformMessage"] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: Any = None  # 原始平台消息对象，仅用于调试
