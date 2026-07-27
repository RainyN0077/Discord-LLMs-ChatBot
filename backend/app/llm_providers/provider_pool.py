"""Provider 连接池 — 管理多个 LLMProvider 实例，提供健康检查和熔断.

功能:
- 实例缓存复用（委托给 factory 模块）
- 周期性健康检查
- 自动熔断（连续 N 次失败后暂停使用）
- 并发请求数限制（per-provider 配额）
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .factory import get_llm_provider

logger = logging.getLogger(__name__)


class ProviderPool:
    """Provider 连接池.

    管理多个 LLMProvider 实例，提供健康检查缓存、自动熔断和并发控制。
    """

    def __init__(
        self,
        max_concurrent_per_provider: int = 5,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_reset_seconds: float = 60.0,
        health_check_interval_seconds: float = 300.0,
    ) -> None:
        """初始化 Provider 连接池.

        Args:
            max_concurrent_per_provider: 每个 Provider 的最大并发数
            circuit_breaker_threshold: 熔断器触发阈值（连续失败次数）
            circuit_breaker_reset_seconds: 熔断器自动重置时间（秒）
            health_check_interval_seconds: 健康检查缓存时间（秒）
        """
        self._max_concurrent = max_concurrent_per_provider
        self._circuit_threshold = circuit_breaker_threshold
        self._circuit_reset = circuit_breaker_reset_seconds
        self._health_interval = health_check_interval_seconds
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self._health_cache: Dict[str, Dict[str, Any]] = {}
        self._health_cache_time: Dict[str, float] = {}
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "requests": 0,
                "errors": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        )
        self._lock = asyncio.Lock()

    def _get_config_key(self, config: Dict[str, Any]) -> str:
        """生成配置唯一键.

        Args:
            config: LLM 配置字典

        Returns:
            配置键，格式为 "provider:model"
        """
        provider = config.get("llm_provider", "openai").lower()
        model = config.get("model_name", "unknown")
        return f"{provider}:{model}"

    async def execute(
        self,
        config: Dict[str, Any],
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None,
    ) -> Any:
        """在池中安全执行 LLM 调用.

        返回 async generator（不消费），调用方自行迭代。
        包含熔断检查、并发控制和错误统计。

        Args:
            config: LLM 配置字典
            messages: 消息列表
            images: 图片字节列表（可选）
            tools: 工具定义列表（可选）
            tool_functions: 工具函数映射（可选）

        Returns:
            async generator，产出 (resp_type, data) 元组

        Raises:
            RuntimeError: 熔断器打开时抛出
        """
        config_key = self._get_config_key(config)

        # 熔断检查
        cb = self._circuit_breakers.get(config_key)
        if cb and cb.get("open", False):
            if time.monotonic() - cb.get("last_failure", 0) > self._circuit_reset:
                cb["open"] = False
                cb["failure_count"] = 0
            else:
                raise RuntimeError(f"Circuit breaker open for {config_key}")

        # 创建信号量
        if config_key not in self._semaphores:
            self._semaphores[config_key] = asyncio.Semaphore(
                self._max_concurrent
            )

        provider = get_llm_provider(config)

        async with self._semaphores[config_key]:
            try:
                self._stats[config_key]["requests"] += 1
                # get_response_stream 是 async generator，不能 await，直接返回
                return provider.get_response_stream(
                    messages, images, tools, tool_functions
                )
            except Exception as e:
                self._stats[config_key]["errors"] += 1
                async with self._lock:
                    cb = self._circuit_breakers.setdefault(
                        config_key,
                        {
                            "failure_count": 0,
                            "last_failure": 0,
                            "open": False,
                        },
                    )
                    cb["failure_count"] += 1
                    cb["last_failure"] = time.monotonic()
                    if cb["failure_count"] >= self._circuit_threshold:
                        cb["open"] = True
                        logger.warning(
                            "Circuit breaker OPEN for %s", config_key
                        )
                raise

    async def collect_full_response(
        self,
        config: Dict[str, Any],
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None,
    ) -> tuple:
        """执行 LLM 调用并收集完整响应.

        消费 execute() 返回的 async generator，收集完整文本和用量数据。

        Args:
            config: LLM 配置字典
            messages: 消息列表
            images: 图片字节列表（可选）
            tools: 工具定义列表（可选）
            tool_functions: 工具函数映射（可选）

        Returns:
            (full_response: str, usage_data: Optional[dict])
        """
        generator = await self.execute(config, messages, images, tools, tool_functions)
        full_response = ""
        usage_data = None
        async for resp_type, data in generator:
            if resp_type == "final":
                full_response = data
            elif resp_type == "usage":
                usage_data = data
        return full_response, usage_data

    async def check_provider_health(
        self, config: Dict[str, Any], force: bool = False
    ) -> Dict[str, Any]:
        """检查指定配置的 Provider 健康状态.

        结果会缓存，避免频繁检查。

        Args:
            config: LLM 配置字典
            force: 是否强制刷新缓存

        Returns:
            健康检查结果字典
        """
        config_key = self._get_config_key(config)
        now = time.monotonic()

        if not force and config_key in self._health_cache_time:
            if now - self._health_cache_time[config_key] < self._health_interval:
                return self._health_cache[config_key]

        provider = get_llm_provider(config)
        if hasattr(provider, "check_health"):
            try:
                health = await provider.check_health()
            except Exception as e:
                health = {"healthy": False, "error": str(e)}
        else:
            health = {"healthy": None, "error": "Provider does not support health check"}

        self._health_cache[config_key] = health
        self._health_cache_time[config_key] = now
        return health

    def get_stats(self) -> Dict[str, Any]:
        """获取所有 Provider 的统计信息.

        Returns:
            配置键到统计信息的映射
        """
        return {key: dict(stats) for key, stats in self._stats.items()}

    def reset_circuit_breaker(self, config_key: str) -> None:
        """手动重置指定配置键的熔断器.

        Args:
            config_key: 配置键（格式 "provider:model"）
        """
        if config_key in self._circuit_breakers:
            self._circuit_breakers[config_key] = {
                "failure_count": 0,
                "last_failure": 0,
                "open": False,
            }
