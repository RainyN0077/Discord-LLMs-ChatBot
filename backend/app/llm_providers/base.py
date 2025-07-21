# backend/app/llm_providers/base.py
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
        self.custom_params = {param["name"]: param["value"] for param in config.get("custom_parameters", [])}
        
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
        # 这是一个生成器，所以需要用 yield 来满足类型提示
        # 实际实现应该在子类中，这里只是为了让 linter 满意
        if False:
            yield "final", "This is an abstract method and should be implemented in subclasses."
        
    def _handle_error(self, e: Exception) -> str:
        """统一处理API调用中的异常，并返回一个带特殊前缀的错误字符串。"""
        error_message = f"LLM_PROVIDER_ERROR: {self.__class__.__name__} encountered an error: {str(e)}"
        logger.error(f"LLM API error in {self.__class__.__name__}: {e}", exc_info=True)
        return error_message