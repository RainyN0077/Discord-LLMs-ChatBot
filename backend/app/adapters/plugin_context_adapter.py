"""插件上下文适配器 — 使旧插件无需修改即可接收 PlatformMessage."""

from typing import Any, Dict, List, Optional, Tuple

from ..ports.platform_message import PlatformMessage
from ..ports.plugin_base import PluginBase


def adapt_message_for_legacy_plugin(message: Any, legacy: bool = False) -> Any:
    """适配消息对象，使旧插件无需修改即可接收 PlatformMessage.

    当 legacy=True 时，将 PlatformMessage 包装为兼容旧插件接口的对象。
    当 legacy=False 时，直接返回原文。

    Args:
        message: 原始消息对象或 PlatformMessage
        legacy: 是否启用旧插件兼容模式

    Returns:
        适配后的消息对象
    """
    if not legacy:
        return message
    if isinstance(message, PlatformMessage):
        return _PlatformMessageLegacyWrapper(message)
    return message


class _PlatformMessageLegacyWrapper:
    """将 PlatformMessage 包装为兼容 discord.Message 接口的对象."""

    def __init__(self, msg: PlatformMessage) -> None:
        """初始化包装器.

        Args:
            msg: PlatformMessage 实例
        """
        self._msg = msg

    @property
    def id(self) -> str:
        """消息 ID."""
        return self._msg.id

    @property
    def content(self) -> str:
        """消息内容."""
        return self._msg.content

    @property
    def author(self) -> "_AuthorWrapper":
        """作者信息."""
        return _AuthorWrapper(self._msg.author)

    @property
    def channel(self) -> "_ChannelWrapper":
        """频道信息."""
        return _ChannelWrapper(self._msg.channel)

    @property
    def guild(self) -> Any:
        """服务器信息."""
        if self._msg.guild:
            return _GuildWrapper(self._msg.guild)
        return None

    @property
    def mentions(self) -> list:
        """提及的用户列表."""
        return [_AuthorWrapper(m) for m in self._msg.mentions]


class _AuthorWrapper:
    """AuthorInfo 包装器，提供类似 discord.User 的接口."""

    def __init__(self, author: Any) -> None:
        """初始化作者包装器.

        Args:
            author: AuthorInfo 实例
        """
        self._author = author

    @property
    def id(self) -> str:
        """用户 ID."""
        return self._author.id

    @property
    def name(self) -> str:
        """用户名."""
        return self._author.name

    @property
    def display_name(self) -> str:
        """显示名称."""
        return self._author.display_name

    @property
    def bot(self) -> bool:
        """是否为 Bot 账号."""
        return self._author.bot


class _ChannelWrapper:
    """ChannelInfo 包装器，提供类似 discord.Channel 的接口."""

    def __init__(self, channel: Any) -> None:
        """初始化频道包装器.

        Args:
            channel: ChannelInfo 实例
        """
        self._channel = channel

    @property
    def id(self) -> str:
        """频道 ID."""
        return self._channel.id

    @property
    def name(self) -> str:
        """频道名称."""
        return self._channel.name


class _GuildWrapper:
    """GuildInfo 包装器，提供类似 discord.Guild 的接口."""

    def __init__(self, guild: Any) -> None:
        """初始化服务器包装器.

        Args:
            guild: GuildInfo 实例
        """
        self._guild = guild

    @property
    def id(self) -> str:
        """服务器 ID."""
        return self._guild.id


class NBPluginAdapter(PluginBase):
    """适配器：将旧 BasePlugin 包装为新的 PluginBase.

    委托给旧 BasePlugin.handle_message()，
    传入 PlatformMessage（作为 Any 兼容）。
    """

    def __init__(
        self,
        inner_plugin: Any,
        plugin_config: Dict[str, Any],
        llm_caller: Optional[callable] = None,
    ) -> None:
        super().__init__(plugin_config, llm_caller)
        self._inner = inner_plugin

    async def handle_message(
        self,
        message: PlatformMessage,
        bot_config: Dict[str, Any],
    ) -> Optional[Tuple[str, List[str]] | bool]:
        """委托给旧插件的 handle_message，使用 Legacy Wrapper 保持兼容."""
        legacy_message = adapt_message_for_legacy_plugin(message, legacy=True)
        return await self._inner.handle_message(legacy_message, bot_config)

    def get_tools(self) -> List[Dict[str, Any]]:
        """委托给旧插件的 get_tools."""
        return self._inner.get_tools()

    def get_tool_functions(self) -> Dict[str, callable]:
        """委托给旧插件的 get_tool_functions."""
        return self._inner.get_tool_functions()


def wrap_plugin(
    plugin_instance: Any,
    plugin_config: Dict[str, Any],
    llm_caller: Optional[callable] = None,
) -> PluginBase:
    """将旧 BasePlugin 包装为新的 PluginBase.

    如果已经是 PluginBase 则直接返回。

    Args:
        plugin_instance: 插件实例
        plugin_config: 插件配置
        llm_caller: LLM 调用函数

    Returns:
        PluginBase 实例
    """
    if isinstance(plugin_instance, PluginBase):
        return plugin_instance
    return NBPluginAdapter(plugin_instance, plugin_config, llm_caller)
