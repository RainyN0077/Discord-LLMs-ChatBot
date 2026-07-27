"""Discord 平台适配器 — 将 Discord 事件转换为 PlatformMessage."""

from typing import Any, Dict, Optional

from ..ports.platform_adapter import PlatformAdapter
from ..ports.platform_message import (
    AttachmentInfo,
    AuthorInfo,
    ChannelInfo,
    GuildInfo,
    PlatformMessage,
)
from ..ports.bot_runtime import BotRuntime


class DiscordPlatformAdapter(PlatformAdapter):
    """适配器: Discord → PlatformMessage."""

    async def event_to_message(
        self,
        event: Any,
        runtime: BotRuntime,
    ) -> Optional[PlatformMessage]:
        """将 Discord MessageEvent 转换为平台无关消息.

        Args:
            event: Discord MessageEvent 对象
            runtime: Bot 运行时实例

        Returns:
            转换后的 PlatformMessage，返回 None 表示事件应被过滤
        """
        # 自过滤: 不处理 Bot 自己的消息
        author = getattr(event, "author", None)
        author_id = str(author.id) if author else ""
        if author_id and author_id == runtime.self_id:
            return None

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
            author = AuthorInfo(id=author_id or "unknown", name="Unknown")

        channel = ChannelInfo(id=str(getattr(event, "channel_id", "")))

        guild = None
        guild_id = getattr(event, "guild_id", None)
        if guild_id:
            guild = GuildInfo(id=str(guild_id))

        mentions = []
        for u in getattr(event, "mentions", []) or []:
            mentions.append(
                AuthorInfo(
                    id=str(u.id),
                    name=u.username,
                    display_name=getattr(u, "global_name", None) or u.username,
                )
            )

        attachments = []
        for a in getattr(event, "attachments", []) or []:
            attachments.append(
                AttachmentInfo(
                    url=str(a.url),
                    filename=getattr(a, "filename", ""),
                    content_type=getattr(a, "content_type", ""),
                )
            )

        return PlatformMessage(
            id=str(getattr(event, "id", "")),
            content=getattr(event, "content", "") or "",
            author=author,
            channel=channel,
            guild=guild,
            mentions=mentions,
            attachments=attachments,
            raw=event,
        )

    def get_platform_name(self) -> str:
        """返回平台名称.

        Returns:
            "discord"
        """
        return "discord"

    def get_bot_id_from_event(self, event: Any) -> Optional[str]:
        """从事件中提取 Bot ID.

        Args:
            event: Discord 事件对象

        Returns:
            当前返回 None，由后续 Wave 实现
        """
        return None

    def is_triggered(
        self, message: PlatformMessage, config: Dict[str, Any]
    ) -> bool:
        """判断是否应对此消息做出响应.

        留空实现，由后续 Wave 完成。

        Args:
            message: 平台无关消息
            config: Bot 配置

        Returns:
            默认返回 True 以保持兼容
        """
        return True
