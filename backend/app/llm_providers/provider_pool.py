"""Provider 连接池 — 管理多个 LLMProvider 实例，提供健康检查和熔断.

功能:
- 实例缓存复用（委托给 factory 模块）
- 周期性健康检查
- 自动熔断（连续 N 次失败后暂停使用）
- 并发请求数限制（per-provider 配额）

P0 修复 (Issue #7):
- 信号量在**迭代期间**持有，而非仅在 execute() 调用点 —— 修复并发限制失效
- 流式迭代中的异常会计数并触发熔断（此前仅在生成器创建时计数）
- 调用点只读拒绝（Q-H1）：熔断打开时抛 RuntimeError，不重置/不计数/不置标志
- 半开探测单飞（Q-L1）：窗口过期后首个迭代放行探测，探测在途时其他迭代
  被拒绝（不计 errors、不更新 last_failure）

MEDIUM 修复:
- 收敛改为"无异常即收敛"（MEDIUM-2）：调用方 break/close 提前终止不再跳过收敛重置，
  半开探测成功后熔断器立即闭合。显式 aclose 走 GeneratorExit 路径；事件循环 finalizer
  （3.12+ create_task(aclose) 被取消）从非消费方任务投递 CancelledError 同样收敛；
  真实用户取消（消费方任务投递）保持不收敛语义
- provider 层吞异常为 "final"+LLM_PROVIDER_ERROR 前缀时计数熔断（MEDIUM-3），
  不打断输出契约
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .base import normalize_provider_name
from .factory import get_llm_provider

logger = logging.getLogger(__name__)

# 服务端错误信号前缀 — 与 LLMProvider._handle_error (base.py) 的输出契约保持一致。
# provider 层将异常吞为 ("final", "LLM_PROVIDER_ERROR: ...")，pool 借此计数熔断 (MEDIUM-3)。
ERROR_PREFIX = "LLM_PROVIDER_ERROR:"


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
        provider = normalize_provider_name(config.get("llm_provider"))
        model = config.get("model_name", "unknown")
        return f"{provider}:{model}"

    @staticmethod
    def _new_circuit_breaker() -> Dict[str, Any]:
        """返回新的熔断器状态字典（全零初始态）.

        Returns:
            {"failure_count": 0, "last_failure": 0, "open": False,
             "probe_in_flight": False}
        """
        return {
            "failure_count": 0,
            "last_failure": 0,
            "open": False,
            "probe_in_flight": False,
        }

    async def execute(
        self,
        config: Dict[str, Any],
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None,
    ) -> Any:
        """在池中安全执行 LLM 调用（返回包装 async generator）.

        信号量在**迭代期间**持有（修复并发限制失效）；迭代异常计数并触发熔断
        后重新抛出（修复流式异常不计数）。

        Args:
            config: LLM 配置字典
            messages: 消息列表
            images: 图片字节列表（可选）
            tools: 工具定义列表（可选）
            tool_functions: 工具函数映射（可选）

        Returns:
            包装后的 async generator，产出 (resp_type, data) 元组

        Raises:
            RuntimeError: 熔断器打开且未到重置窗口（调用点只读拒绝，零副作用）;
                         半开探测在途时首迭代拒绝（不计 errors）
        """
        config_key = self._get_config_key(config)

        # 调用点: 只读拒绝 (Q-H1) — 不重置/不计数/不置标志
        cb = self._circuit_breakers.get(config_key)
        if cb and cb.get("open", False):
            if time.monotonic() - cb.get("last_failure", 0) <= self._circuit_reset:
                raise RuntimeError(f"Circuit breaker open for {config_key}")

        if config_key not in self._semaphores:
            self._semaphores[config_key] = asyncio.Semaphore(self._max_concurrent)
        sem = self._semaphores[config_key]

        provider = get_llm_provider(config)
        raw_generator = provider.get_response_stream(messages, images, tools, tool_functions)

        async def _wrapped_generator():
            # 首迭代（锁内）: 半开单飞准入
            async with self._lock:
                cb = self._circuit_breakers.setdefault(config_key, self._new_circuit_breaker())
                if cb["open"] and (time.monotonic() - cb.get("last_failure", 0)) > self._circuit_reset:
                    if cb.get("probe_in_flight", False):
                        # 半开拒绝 (B 路径): 不计 errors、不更新 last_failure (Q-L1)
                        raise RuntimeError(f"Circuit breaker half-open, probe in flight for {config_key}")
                    cb["probe_in_flight"] = True
                    logger.info("Circuit breaker half-open probe for %s", config_key)

            # 迭代: 并发控制覆盖完整消费
            async with sem:
                self._stats[config_key]["requests"] += 1
                failed = False
                consumer_task = None
                try:
                    async for resp_type, data in raw_generator:
                        consumer_task = asyncio.current_task()
                        if resp_type == "final" and isinstance(data, str) and data.startswith(ERROR_PREFIX):
                            # 服务端错误信号 (MEDIUM-3): 计数熔断但不打断输出契约
                            failed = True
                            async with self._lock:
                                cb = self._circuit_breakers.setdefault(config_key, self._new_circuit_breaker())
                                cb["failure_count"] += 1
                                cb["last_failure"] = time.monotonic()
                                if cb["failure_count"] >= self._circuit_threshold:
                                    cb["open"] = True
                                    logger.warning("Circuit breaker OPEN for %s", config_key)
                                self._stats[config_key]["errors"] += 1
                        yield resp_type, data
                except asyncio.CancelledError:
                    # 取消/关闭: 不计数不熔断。
                    # 真实任务取消（CancelledError 由消费方任务投递）→ 不收敛（等待下个探测）；
                    # 事件循环 finalizer 在其他任务中执行 aclose（3.12+ 为 create_task(aclose)
                    # 后任务被取消，CancelledError 从非消费方任务投递）→ 流无失败证据 → 收敛
                    if consumer_task is not None and asyncio.current_task() is consumer_task:
                        failed = True
                    raise
                except Exception:
                    failed = True
                    async with self._lock:
                        cb = self._circuit_breakers.setdefault(config_key, self._new_circuit_breaker())
                        cb["failure_count"] += 1
                        cb["last_failure"] = time.monotonic()
                        cb["probe_in_flight"] = False
                        if cb["failure_count"] >= self._circuit_threshold:
                            cb["open"] = True
                            logger.warning("Circuit breaker OPEN for %s", config_key)
                        self._stats[config_key]["errors"] += 1
                    raise
                finally:
                    # 兜底: 清悬挂探测标志（含调用方 break/close 提前终止）
                    try:
                        async with self._lock:
                            cb = self._circuit_breakers.get(config_key)
                            if cb and cb.get("probe_in_flight", False):
                                cb["probe_in_flight"] = False
                    except asyncio.CancelledError:
                        raise
                    # 无异常（含调用方 break/close 提前终止）→ 收敛重置 (MEDIUM-2)
                    if not failed:
                        try:
                            async with self._lock:
                                cb = self._circuit_breakers.setdefault(config_key, self._new_circuit_breaker())
                                cb["open"] = False
                                cb["failure_count"] = 0
                                cb["probe_in_flight"] = False
                        except asyncio.CancelledError:
                            raise

        return _wrapped_generator()

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
            self._circuit_breakers[config_key] = self._new_circuit_breaker()
