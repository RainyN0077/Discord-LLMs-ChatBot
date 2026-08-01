"""LLM Provider 增强接口 — 定义健康检查和配额信息契约.

用于解耦 LLM 提供商的可观测性需求。

实现状态: ProviderHealth/QuotaInfo 契约已由 ``llm_providers.base.LLMProvider``
（显式继承）及各具体提供商实现，不再是未来 Wave 的占位接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class ProviderHealth(ABC):
    """提供商健康检查接口."""

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """返回健康状态.

        Returns:
            {
                "healthy": bool,
                "latency_ms": Optional[float],
                "model": str,
                "error": Optional[str],
            }
        """
        ...


class QuotaInfo(ABC):
    """提供商配额信息接口."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """返回提供商名称."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回模型名称."""
        ...

    @abstractmethod
    async def get_usage_stats(self) -> Dict[str, Any]:
        """返回用量统计.

        Returns:
            {
                "total_requests": int,
                "total_input_tokens": int,
                "total_output_tokens": int,
                "last_request_at": Optional[str],
                "errors_last_hour": int,
            }
        """
        ...
