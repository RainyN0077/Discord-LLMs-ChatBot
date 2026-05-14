from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from nonebot.adapters.discord import Bot, MessageEvent


@dataclass
class AuthorContext:
    id: int
    name: str
    display_name: str
    roles: List[Any] = field(default_factory=list)

    def __bool__(self) -> bool:
        return True

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def bot(self) -> bool:
        return False


@dataclass
class ChannelContext:
    id: int
    name: str = ""


@dataclass
class GuildContext:
    id: int
    name: str = ""


@dataclass
class AttachmentContext:
    url: str
    filename: str = ""
    content_type: str = ""


@dataclass
class MentionContext:
    id: int
    name: str

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def bot(self) -> bool:
        return False


@dataclass
class EmbedContext:
    type: str = ""
    url: Optional[str] = None
    thumbnail: Any = None
    image: Any = None


@dataclass
class StickerContext:
    url: str = ""


@dataclass
class ReplyContext:
    resolved: Optional[Any] = None


@dataclass
class MessageContext:
    id: int
    content: str
    author: AuthorContext
    channel: ChannelContext
    guild: Optional[GuildContext] = None
    mentions: List[MentionContext] = field(default_factory=list)
    attachments: List[AttachmentContext] = field(default_factory=list)
    embeds: List[EmbedContext] = field(default_factory=list)
    stickers: List[StickerContext] = field(default_factory=list)
    reference: Optional[ReplyContext] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def event_to_message_context(event: MessageEvent, bot: Bot) -> MessageContext:
    author = AuthorContext(
        id=event.author.id,
        name=event.author.username,
        display_name=getattr(event.author, "global_name", None) or event.author.username,
    )

    channel = ChannelContext(id=event.channel_id)

    guild = None
    if getattr(event, "guild_id", None):
        guild = GuildContext(id=event.guild_id)

    mentions = []
    if event.mentions:
        mentions = [MentionContext(id=u.id, name=u.username) for u in event.mentions]

    attachments = []
    if event.attachments:
        attachments = [
            AttachmentContext(
                url=a.url,
                filename=getattr(a, "filename", ""),
                content_type=getattr(a, "content_type", ""),
            )
            for a in event.attachments
        ]

    reference = None
    if getattr(event, "reply", None):
        ref_msg = event.reply
        ref_author = AuthorContext(
            id=ref_msg.author.id,
            name=ref_msg.author.username,
            display_name=getattr(ref_msg.author, "global_name", None) or ref_msg.author.username,
        )
        ref_channel = ChannelContext(id=event.channel_id)
        resolved = MessageContext(
            id=ref_msg.id,
            content=getattr(ref_msg, "content", ""),
            author=ref_author,
            channel=ref_channel,
        )
        reference = ReplyContext(resolved=resolved)

    return MessageContext(
        id=event.id,
        content=event.content or "",
        author=author,
        channel=channel,
        guild=guild,
        mentions=mentions,
        attachments=attachments,
        reference=reference,
    )
