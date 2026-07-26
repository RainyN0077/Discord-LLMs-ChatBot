# backend/app/llm_providers/base.py
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, AsyncGenerator, Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
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