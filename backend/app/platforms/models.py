from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlatformUser:
    id: str
    name: str
    display_name: str = ""
    platform: str = "unknown"
    is_bot: bool = False


@dataclass
class PlatformChannel:
    id: str
    name: str = ""
    platform: str = "unknown"


@dataclass
class PlatformGuild:
    id: str
    name: str = ""
    platform: str = "unknown"


@dataclass
class PlatformMessage:
    id: str
    content: str
    clean_content: str
    author: PlatformUser
    channel: PlatformChannel
    guild: Optional[PlatformGuild] = None
    mentions: List[PlatformUser] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    reference: Optional[Dict[str, Any]] = None
    platform: str = "discord"
    raw_data: Dict[str, Any] = field(default_factory=dict)
