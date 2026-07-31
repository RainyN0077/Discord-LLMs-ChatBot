# backend/app/llm_providers/base.py
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, AsyncGenerator, Tuple, Optional, Union
import logging

from ..ports.llm_provider import ProviderHealth, QuotaInfo

logger = logging.getLogger(__name__)


def normalize_provider_name(name: Optional[str]) -> str:
    """归一化提供商名称 — 与 factory 完全一致的归一化唯一来源.

    ``None``/空值回退为 ``"openai"``；``"xai"`` 映射为 ``"grok"``（工厂内部
    使用 grok 作为 xAI 提供商的注册名）；其余名称原样小写返回。

    Args:
        name: 配置中的提供商名称（可为 None/非 str）

    Returns:
        归一化后的提供商名称
    """
    normalized = (name or "openai").lower()
    if normalized == "xai":
        return "grok"
    return normalized


class LLMProvider(ProviderHealth, QuotaInfo, ABC):
    """
    抽象基类，定义了所有LLM提供商的统一接口。
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
        self.model = config.get("model_name")
        self.stream = config.get("stream_response", True)
        self.temperature = config.get("temperature")
        self.max_tokens = config.get("max_tokens")
        self.top_p = config.get("top_p")
        self.top_k = config.get("top_k")
        self.frequency_penalty = config.get("frequency_penalty")
        self.presence_penalty = config.get("presence_penalty")
        self.custom_headers = config.get("custom_headers", [])
        self.custom_params = {param["name"]: param["value"] for param in config.get("custom_parameters", [])}

    @property
    def provider_name(self) -> str:
        """返回归一化提供商名称 (xai → grok)."""
        return normalize_provider_name(self.config.get("llm_provider"))

    @property
    def model_name(self) -> str:
        """返回生效模型名: openai_model_name 优先, 回退 model_name (factory 语义)."""
        return (self.config.get("openai_model_name") or self.config.get("model_name") or "")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.model!r}>"
        
    @abstractmethod
    async def get_response_stream(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None
    ) -> AsyncGenerator[Tuple[str, Union[str, Dict[str, int]]], None]:
        """
        获取LLM响应的异步生成器，支持工具调用和用量返回。

        Args:
            messages (List[Dict[str, Any]]): 发送给LLM的消息列表。
            images (Optional[List[bytes]]): 附加的图片数据列表。
            tools (Optional[List[Dict[str, Any]]]): 可供LLM调用的工具列表。
            tool_functions (Optional[Dict[str, callable]]): 工具名到可执行函数的映射。

        Yields:
            Tuple[str, Union[str, Dict[str, int]]]: 一个元组，第一个元素是响应类型:
              - "partial": 第二个元素是部分文本内容(str)
              - "final": 第二个元素是最终文本内容(str)
              - "usage": 第二个元素是用量数据字典(Dict[str, int])
        """
        raise NotImplementedError("Subclasses must implement get_response_stream")
        
    def _build_api_kwargs(self, model, messages, stream, **extra):
        kwargs = {"model": model, "messages": messages, "stream": stream}
        if self.temperature is not None: kwargs["temperature"] = self.temperature
        if self.max_tokens is not None: kwargs["max_tokens"] = self.max_tokens
        if self.top_p is not None: kwargs["top_p"] = self.top_p
        if self.top_k is not None: kwargs["top_k"] = self.top_k
        if self.frequency_penalty is not None: kwargs["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None: kwargs["presence_penalty"] = self.presence_penalty
        kwargs.update(self.custom_params)
        kwargs.update(extra)
        return kwargs

    def _handle_error(self, e: Exception) -> str:
        """统一处理API调用中的异常，并返回一个带特殊前缀的错误字符串。"""
        error_message = f"LLM_PROVIDER_ERROR: {self.__class__.__name__} encountered an error: {str(e)}"
        logger.error(f"LLM API error in {self.__class__.__name__}: {e}", exc_info=True)
        return error_message

    async def check_health(self) -> Dict[str, Any]:
        """检查 LLM 提供商健康状态.

        默认实现：发送一条简单的测试消息。
        子类可重写以实现更精确的检查（如轻量级 endpoint 探测）。

        Returns:
            {
                "healthy": bool,
                "latency_ms": Optional[float],
                "model": str,
                "error": Optional[str],
            }
        """
        start = time.monotonic()
        try:
            test_messages = [{"role": "user", "content": "ping"}]
            async for response_type, data in self.get_response_stream(
                messages=test_messages, images=None, tools=[], tool_functions={},
            ):
                if response_type == "final":
                    latency_ms = round((time.monotonic() - start) * 1000, 2)
                    return {
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "model": self.model or "unknown",
                        "error": None,
                    }
                if response_type == "usage":
                    continue
            return {
                "healthy": False,
                "latency_ms": None,
                "model": self.model or "unknown",
                "error": "No response from provider",
            }
        except Exception as e:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            return {
                "healthy": False,
                "latency_ms": latency_ms,
                "model": self.model or "unknown",
                "error": str(e),
            }

    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取提供商用量统计（默认实现）.

        子类可重写以返回实际统计数据。

        Returns:
            用量统计字典
        """
        return {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "last_request_at": None,
            "errors_last_hour": 0,
        }