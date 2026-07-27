"""LLM Provider 增强接口 — 定义健康检查和配额信息契约.

用于解耦 LLM 提供商的可观测性需求。

NOTE: ProviderHealth and QuotaInfo are interface definitions for future waves.
In Wave 1, only the contract is defined. Implementation will come in Wave 3.
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
    def get_usage_stats(self) -> Dict[str, Any]:
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
