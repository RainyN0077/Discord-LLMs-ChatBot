"""向后兼容层：旧 MessageContext → 新 PlatformMessage.

Phase 1: 提供 MessageContext 别名指向 PlatformMessage，以及 event_to_message_context 兼容函数。
Phase 2 (USE_NEW_MAIN_PIPELINE = True 后): 删除此文件，所有引用直接使用 PlatformMessage。
"""

from types import SimpleNamespace
from typing import Any, List, Optional

from app.ports.platform_message import (
    AttachmentInfo,
    AuthorInfo,
    ChannelInfo,
    GuildInfo,
    PlatformMessage,
)

# MessageContext 别名 — Phase 2 后移除
MessageContext = PlatformMessage


def event_to_message_context(event: Any, bot: Any) -> PlatformMessage:
    """临时兼容函数 — Phase 2 后移除.

    将 Discord MessageEvent 转换为 PlatformMessage。
    动态添加旧 MessageContext 拥有的字段以便向後兼容。

    Args:
        event: Discord MessageEvent 对象
        bot: NoneBot Bot 实例（已弃用，仅保留签名兼容）

    Returns:
        PlatformMessage 实例
    """
    has_author = getattr(event, "author", None) is not None
    if has_author:
        author = AuthorInfo(
            id=str(event.author.id),
            name=event.author.username,
            display_name=(
                getattr(event.author, "global_name", None) or event.author.username
            ),
            roles=[str(r.id) for r in getattr(event.author, "roles", []) or []],
        )
    else:
        author = AuthorInfo(id="unknown", name="Unknown")

    channel = ChannelInfo(id=str(getattr(event, "channel_id", "")))

    guild = None
    guild_id = getattr(event, "guild_id", None)
    if guild_id:
        guild = GuildInfo(id=str(guild_id))

    mentions: List[AuthorInfo] = []
    for u in getattr(event, "mentions", []) or []:
        mentions.append(
            AuthorInfo(
                id=str(u.id),
                name=u.username,
                display_name=getattr(u, "global_name", None) or u.username,
            )
        )

    attachments: List[AttachmentInfo] = []
    for a in getattr(event, "attachments", []) or []:
        attachments.append(
            AttachmentInfo(
                url=str(a.url),
                filename=getattr(a, "filename", ""),
                content_type=getattr(a, "content_type", ""),
            )
        )

    msg = PlatformMessage(
        id=str(getattr(event, "id", "")),
        content=getattr(event, "content", "") or "",
        author=author,
        channel=channel,
        guild=guild,
        mentions=mentions,
        attachments=attachments,
        raw=event,
    )

    # --- 向后兼容属性（Phase 2 后移除）---
    # PlatformMessage 没有 embeds/stickers 字段，但旧 MessageContext 有，
    # 下游代码（image_processor.collect_image_descriptors）会访问它们
    msg.embeds: List[Any] = []
    msg.stickers: List[Any] = []

    # 旧代码通过 .reference 和 .reference.resolved 访问回复消息
    # 例如 persona_manager.py: message.reference  /  context_builder.py: message.reference.resolved
    # 始终设置 reference，无回复时设为 None
    reply = getattr(event, "reply", None)
    if reply is not None:
        ref_author_id = "0"
        ref_author_name = "Unknown"
        if hasattr(reply, "author"):
            ref_author_id = str(reply.author.id)
            ref_author_name = reply.author.username
        ref_author = AuthorInfo(
            id=ref_author_id,
            name=ref_author_name,
            display_name=(
                getattr(reply.author, "global_name", None) or ref_author_name
            )
            if hasattr(reply, "author")
            else ref_author_name,
        )
        ref_channel = ChannelInfo(id=str(getattr(event, "channel_id", "")))

        ref_platform_msg = PlatformMessage(
            id=str(reply.id),
            content=getattr(reply, "content", ""),
            author=ref_author,
            channel=ref_channel,
            raw=reply,
        )
        # 回复消息也设置向后兼容属性
        ref_platform_msg.embeds = []
        ref_platform_msg.stickers = []

        msg.reply_to = ref_platform_msg
        msg.reference = SimpleNamespace(resolved=ref_platform_msg)
    else:
        # 无回复时也设置 reference=None 以避免 AttributeError
        msg.reference = None
    # --- 向后兼容属性结束 ---

    return msg
