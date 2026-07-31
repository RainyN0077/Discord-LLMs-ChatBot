"""PluginRegistry 测试 — 注册/注销/处理语义 + discover_and_load legacy 回退 (Task 1.4.4)."""
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.adapters.plugin_context_adapter import NBPluginAdapter
from app.ports.plugin_base import PluginBase
from app.ports.platform_message import AuthorInfo, ChannelInfo, PlatformMessage
from app.ports.plugin_registry import PluginRegistry

# ---------------------------------------------------------------------------
# 测试用插件类
# ---------------------------------------------------------------------------


class OverridePlugin(PluginBase):
    """override 模式插件: 触发后短路后续处理."""

    def __init__(self, plugin_config=None, llm_caller=None) -> None:
        super().__init__(plugin_config or {}, llm_caller)
        self.called = 0

    async def handle_message(self, message, bot_config):
        self.called += 1
        return True


class AppendPlugin(PluginBase):
    """append 模式插件: 返回注入数据."""

    def __init__(self, plugin_config=None, llm_caller=None, data: str = "data") -> None:
        super().__init__(plugin_config or {}, llm_caller)
        self.data = data
        self.called = 0

    async def handle_message(self, message, bot_config):
        self.called += 1
        return ("append", [self.data])


class FailingPlugin(PluginBase):
    """抛异常的插件: 不应中断其他插件处理."""

    async def handle_message(self, message, bot_config):
        raise RuntimeError("boom")


class MemoryToolsPlugin(PluginBase):
    """模拟 memory_plugin 的工具函数（name 强制为 memory_plugin）."""

    def __init__(self, plugin_config=None, llm_caller=None) -> None:
        super().__init__(plugin_config or {}, llm_caller)
        self.name = "memory_plugin"

    async def handle_message(self, message, bot_config):
        return None

    def get_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "memory_tool"}]

    def get_tool_functions(self) -> Dict[str, callable]:
        return {
            "add_to_memory": self._add_to_memory,
            "add_to_world_book": self._add_to_world_book,
        }

    def _add_to_memory(self, message=None, config=None, user_id=None, user_name=None, **kwargs):
        return {"message": message, "config": config, "user_id": user_id, "user_name": user_name, "kwargs": kwargs}

    def _add_to_world_book(self, message=None, config=None, user_id=None, user_name=None, **kwargs):
        return {"message": message, "config": config, "user_id": user_id, "user_name": user_name, "kwargs": kwargs}


@pytest.fixture
def msg() -> PlatformMessage:
    return PlatformMessage(
        id="msg-1",
        content="hello",
        author=AuthorInfo(id="user-1", name="User", display_name="User"),
        channel=ChannelInfo(id="chan-1"),
    )


# ---------------------------------------------------------------------------
# 注册/注销/快照
# ---------------------------------------------------------------------------


class TestRegistryBasics:
    def test_register_get_get_all(self):
        registry = PluginRegistry()
        plugin = AppendPlugin()
        registry.register("append_plugin", plugin)
        assert registry.get("append_plugin") is plugin
        assert registry.get("missing") is None
        assert registry.get_all() == [plugin]
        assert registry.get_all_snapshot() == [plugin]
        # get_all 返回副本
        registry.get_all()[0] = None
        assert registry.get_all() == [plugin]

    def test_unregister(self):
        registry = PluginRegistry()
        plugin = AppendPlugin()
        registry.register("append_plugin", plugin)
        registry.register("other", plugin)
        registry.unregister("append_plugin")
        assert registry.get("append_plugin") is None
        assert registry.get_all() == [plugin]


# ---------------------------------------------------------------------------
# process_message 语义
# ---------------------------------------------------------------------------


class TestProcessMessage:
    async def test_override_short_circuits_later_plugins(self, msg):
        registry = PluginRegistry()
        override = OverridePlugin()
        append = AppendPlugin()
        registry.register("override", override)
        registry.register("append", append)
        result = await registry.process_message(msg, {})
        assert result is True
        assert append.called == 0  # override 短路，后续插件未调用

    async def test_append_aggregates(self, msg):
        registry = PluginRegistry()
        registry.register("p1", AppendPlugin(data="a"))
        registry.register("p2", AppendPlugin(data="b"))
        result = await registry.process_message(msg, {})
        assert result == ("append", ["a", "b"])

    async def test_plugin_exception_does_not_interrupt(self, msg):
        registry = PluginRegistry()
        registry.register("failing", FailingPlugin({}))
        registry.register("append", AppendPlugin(data="ok"))
        result = await registry.process_message(msg, {})
        assert result == ("append", ["ok"])

    async def test_enabled_false_skipped(self, msg):
        registry = PluginRegistry()
        plugin = AppendPlugin()
        plugin.enabled = False
        registry.register("p", plugin)
        result = await registry.process_message(msg, {})
        assert result is None

    async def test_no_trigger_returns_none(self, msg):
        registry = PluginRegistry()
        result = await registry.process_message(msg, {})
        assert result is None


# ---------------------------------------------------------------------------
# 工具聚合
# ---------------------------------------------------------------------------


class TestToolAggregation:
    def test_get_all_tools_aggregates(self):
        registry = PluginRegistry()
        registry.register("a", AppendPlugin())
        registry.register("m", MemoryToolsPlugin())
        names = [tool["name"] for tool in registry.get_all_tools()]
        assert "memory_tool" in names

    async def test_get_all_tool_functions_memory_plugin_partial(self, msg):
        registry = PluginRegistry()
        registry.register("memory_plugin", MemoryToolsPlugin())
        functions = registry.get_all_tool_functions(msg, {"bot": "cfg"})
        assert set(functions.keys()) == {"add_to_memory", "add_to_world_book"}
        result = functions["add_to_memory"](content="remember this")
        assert result["message"] is msg
        assert result["config"] == {"bot": "cfg"}
        assert result["user_id"] == "user-1"
        assert result["user_name"] == "User"
        assert result["kwargs"] == {"content": "remember this"}


# ---------------------------------------------------------------------------
# discover_and_load — 临时 fake plugins 包
# ---------------------------------------------------------------------------


FAKE_PLUGIN_MODULES = {
    "memory_plugin.py": (
        "from app.ports.plugin_base import PluginBase\n"
        "\n"
        "class MemoryPlugin(PluginBase):\n"
        "    async def handle_message(self, message, bot_config):\n"
        "        return None\n"
        "    def get_tools(self):\n"
        "        return [{'name': 'memory_tool'}]\n"
    ),
    "configurable_plugin.py": (
        "from app.ports.plugin_base import PluginBase\n"
        "\n"
        "class ConfigurablePlugin(PluginBase):\n"
        "    async def handle_message(self, message, bot_config):\n"
        "        return ('append', ['from-config'])\n"
    ),
    "legacy_plugin.py": (
        "class LegacyPlugin:\n"
        "    def __init__(self, plugin_config=None, llm_caller=None):\n"
        "        self.plugin_config = plugin_config\n"
        "        self.llm_caller = llm_caller\n"
        "        self.last_message = None\n"
        "    async def handle_message(self, message, bot_config):\n"
        "        self.last_message = message\n"
        "        return True\n"
        "    def get_tools(self):\n"
        "        return [{'name': 'legacy_tool'}]\n"
        "    def get_tool_functions(self):\n"
        "        return {}\n"
    ),
    "noargs_legacy.py": (
        "class NoArgsLegacy:\n"
        "    def __init__(self):\n"
        "        self.calls = 0\n"
        "    async def handle_message(self, message, bot_config):\n"
        "        self.calls += 1\n"
        "        return None\n"
    ),
    "weird_module.py": (
        "async def handle_message(message, bot_config):\n"
        "    return None\n"
    ),
}


@pytest.fixture
def fake_plugins_package(monkeypatch, tmp_path):
    """构造临时 fake plugins 包（磁盘文件 + sys.modules 注册）.

    将真实 plugins 子模块移出 sys.modules，确保 import 命中 fake 文件；
    teardown 时删除 fake 子模块并恢复原状。
    """
    existing_children = {
        name: mod for name, mod in sys.modules.items() if name.startswith("plugins.")
    }
    for name in existing_children:
        del sys.modules[name]

    pkg_dir: Path = tmp_path / "plugins"
    pkg_dir.mkdir(exist_ok=True)
    for filename, source in FAKE_PLUGIN_MODULES.items():
        (pkg_dir / filename).write_text(source, encoding="utf-8")

    pkg = types.ModuleType("plugins")
    pkg.__path__ = [str(pkg_dir)]
    monkeypatch.setitem(sys.modules, "plugins", pkg)

    yield pkg

    for name in [m for m in list(sys.modules) if m.startswith("plugins.")]:
        del sys.modules[name]
    sys.modules.update(existing_children)


class TestDiscoverAndLoad:
    def test_discovers_pluginbase_and_config_plugins(self, fake_plugins_package):
        registry = PluginRegistry()
        registry.discover_and_load(
            {
                "memory_plugin": {},
                "configurable_plugin": {"enabled": True},
                "legacy_plugin": {"enabled": True},
            },
            llm_caller=lambda: None,
        )
        assert "memory_plugin" in registry._loaded_modules  # 强制启用
        assert "configurable_plugin" in registry._loaded_modules
        assert registry.get("memory_plugin") is not None
        assert registry.get("configurable_plugin") is not None

    async def test_legacy_plugin_wrapped_as_nbpluginadapter(self, fake_plugins_package, msg):
        registry = PluginRegistry()
        registry.discover_and_load(
            {"legacy_plugin": {"enabled": True}},
            llm_caller=lambda: None,
        )
        plugin = registry.get("legacy_plugin")
        assert isinstance(plugin, NBPluginAdapter)
        # 委托给 inner，且 message 被包装为 legacy 兼容对象
        result = await plugin.handle_message(msg, {})
        assert result is True
        inner = plugin._inner
        assert inner.last_message is not None
        assert inner.last_message.content == msg.content

    def test_legacy_plugin_typeerror_fallback_noargs(self, fake_plugins_package):
        registry = PluginRegistry()
        registry.discover_and_load(
            {"noargs_legacy": {"enabled": True}},
            llm_caller=lambda: None,
        )
        plugin = registry.get("noargs_legacy")
        assert isinstance(plugin, NBPluginAdapter)
        assert plugin._inner.calls == 0

    def test_disabled_legacy_not_registered(self, fake_plugins_package):
        registry = PluginRegistry()
        registry.discover_and_load(
            {"legacy_plugin": {"enabled": False}},
            llm_caller=lambda: None,
        )
        assert registry.get("legacy_plugin") is None
        assert "legacy_plugin" not in registry._loaded_modules

    def test_non_class_attrs_skipped(self, fake_plugins_package):
        registry = PluginRegistry()
        # 空配置: 避免 config 插件阶段按名注册；仅验证 discovery 跳过非类属性
        registry.discover_and_load({}, llm_caller=lambda: None)
        # 模块级函数 handle_message 不是类 → 跳过，不注册不报错
        assert registry.get("weird_module") is None
        assert "weird_module" not in registry._loaded_modules
