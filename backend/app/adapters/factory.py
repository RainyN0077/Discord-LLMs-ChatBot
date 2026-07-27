"""BotRuntime 工厂 — 根据配置创建对应的 BotRuntime 实例."""

from typing import Any, Dict

from ..ports.bot_runtime import BotRuntime


def create_bot_runtime(bot_id: str, config: Dict[str, Any]) -> BotRuntime:
    """根据配置创建 BotRuntime 实例.

    Args:
        bot_id: Bot 唯一标识符
        config: Bot 配置字典，必须包含 'runtime_type' 字段（默认 "nonebot"）

    Returns:
        BotRuntime 实例

    Raises:
        ValueError: 不支持的 runtime_type
    """
    runtime_type = config.get("runtime_type", "nonebot")

    if runtime_type == "nonebot":
        from .nonebot_runtime import NoneBotRuntime
        return NoneBotRuntime(bot_id, config)
    elif runtime_type == "mock":
        from .mock_bot_runtime import MockBotRuntime
        return MockBotRuntime(bot_id)
    else:
        raise ValueError(
            f"Unsupported runtime_type: '{runtime_type}'. "
            f"Supported values: nonebot, mock"
        )
