"""Feature Flag 配置 — 控制迁移步骤的开闭.

所有 Flag 默认 False（旧代码路径），逐个 Wave 切换为 True。
通过环境变量可覆盖默认值。

环境变量格式: FEATURE_<FLAG_NAME>=1
例如: FEATURE_USE_BOT_RUNTIME_ABSTRACTION=1
"""

import os
from typing import Dict

_FLAGS: Dict[str, bool] = {
    # Wave 1: 新建文件
    "USE_BOT_RUNTIME_ABSTRACTION": False,
    "USE_PLATFORM_MESSAGE_MODEL": False,
    "USE_PLATFORM_ADAPTER": False,
    "USE_ENHANCED_PLUGIN_REGISTRY": False,
    # Wave 2: Feature Flag 替换
    "USE_NEW_PIPELINE_SEND": False,
    "USE_NEW_CONTEXT_BUILDER": False,
    # Wave 3: ProviderPool
    "USE_PROVIDER_POOL": False,
    # Wave 4: 主 pipeline 切换
    "USE_NEW_MAIN_PIPELINE": False,
}


def is_flag_enabled(flag_name: str) -> bool:
    """检查 Feature Flag 是否启用.

    优先级: 环境变量 > 代码默认值。
    环境变量格式: FEATURE_<FLAG_NAME>=1

    Args:
        flag_name: Flag 名称，如 "USE_BOT_RUNTIME_ABSTRACTION"

    Returns:
        Flag 是否启用
    """
    env_key = f"FEATURE_{flag_name}"
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val in ("1", "true", "True", "yes")
    return _FLAGS.get(flag_name, False)


def set_flag(flag_name: str, value: bool) -> None:
    """运行时强制设置 Flag（主要用于测试）.

    Args:
        flag_name: Flag 名称
        value: Flag 值
    """
    _FLAGS[flag_name] = value
