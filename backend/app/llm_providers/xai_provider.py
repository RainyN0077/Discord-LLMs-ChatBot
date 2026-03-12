import base64
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

from xai_sdk.chat import image as xai_image
from xai_sdk.chat import text as xai_text
from xai_sdk.chat import tool as xai_tool
from xai_sdk.chat import tool_result as xai_tool_result
from xai_sdk.proto import chat_pb2

from ..xai_sdk_utils import create_xai_async_client, xai_sampling_usage_to_dict
from .base import LLMProvider

logger = logging.getLogger(__name__)


class XAIProvider(LLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        base_url = config.get("grok_base_url") or self.base_url
        self.client = create_xai_async_client(api_key=self.api_key, base_url=base_url)

    @staticmethod
    def _stringify_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    item_text = item.get("text") or item.get("content")
                    if item_text:
                        text_parts.append(str(item_text))
                else:
                    text_parts.append(str(item))
            return "\n".join(text_parts)
        return str(content)

    def _prepare_messages(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]],
    ) -> List[chat_pb2.Message]:
        prepared: List[chat_pb2.Message] = []
        last_user_index: Optional[int] = None

        for message in messages:
            role = str(message.get("role") or "user").strip().lower()
            text = self._stringify_content(message.get("content", ""))
            content_parts = [xai_text(text)] if text else []

            if role == "system":
                pb_role = chat_pb2.MessageRole.ROLE_SYSTEM
            elif role == "assistant":
                pb_role = chat_pb2.MessageRole.ROLE_ASSISTANT
            elif role == "tool":
                pb_role = chat_pb2.MessageRole.ROLE_TOOL
            else:
                pb_role = chat_pb2.MessageRole.ROLE_USER
                last_user_index = len(prepared)

            prepared.append(
                chat_pb2.Message(
                    role=pb_role,
                    content=content_parts,
                    tool_call_id=str(message.get("tool_call_id") or ""),
                )
            )

        image_parts = [
            xai_image(base64.b64encode(image_bytes).decode("utf-8"))
            for image_bytes in (images or [])
            if image_bytes
        ]
        if image_parts:
            if last_user_index is not None:
                prepared[last_user_index].content.extend(image_parts)
            else:
                prepared.append(
                    chat_pb2.Message(
                        role=chat_pb2.MessageRole.ROLE_USER,
                        content=image_parts,
                    )
                )

        return prepared

    @staticmethod
    def _prepare_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[chat_pb2.Tool]]:
        if not tools:
            return None

        prepared_tools: List[chat_pb2.Tool] = []
        for tool in tools:
            declaration = tool.get("function", tool)
            name = declaration.get("name")
            if not name:
                continue
            prepared_tools.append(
                xai_tool(
                    name=name,
                    description=str(declaration.get("description") or ""),
                    parameters=declaration.get("parameters") or {"type": "object", "properties": {}},
                )
            )

        return prepared_tools or None

    def _chat_kwargs(
        self,
        prepared_messages: List[chat_pb2.Message],
        prepared_tools: Optional[List[chat_pb2.Tool]],
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": prepared_messages,
        }

        allowed_keys = {
            "max_tokens",
            "seed",
            "stop",
            "temperature",
            "top_p",
            "logprobs",
            "top_logprobs",
            "frequency_penalty",
            "presence_penalty",
            "reasoning_effort",
            "parallel_tool_calls",
            "store_messages",
            "use_encrypted_content",
            "max_turns",
            "agent_count",
            "user",
        }
        for key in allowed_keys:
            if key in self.custom_params:
                kwargs[key] = self.custom_params[key]

        if prepared_tools:
            kwargs["tools"] = prepared_tools
            kwargs["tool_choice"] = self.custom_params.get("tool_choice", "auto")

        response_format = self.custom_params.get("response_format")
        if isinstance(response_format, str):
            kwargs["response_format"] = response_format

        return kwargs

    @staticmethod
    def _merge_usage(
        first: Optional[Dict[str, int]],
        second: Optional[Dict[str, int]],
    ) -> Optional[Dict[str, int]]:
        if first and second:
            return {
                "input_tokens": int(first.get("input_tokens", 0)) + int(second.get("input_tokens", 0)),
                "output_tokens": int(first.get("output_tokens", 0)) + int(second.get("output_tokens", 0)),
            }
        return second or first

    @staticmethod
    def _tool_result_payload(result: Any) -> str:
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return str(result)

    def _append_tool_results(self, chat: Any, response: Any, tool_functions: Dict[str, callable]) -> None:
        chat.append(response)

        for tool_call in response.tool_calls:
            function_name = getattr(getattr(tool_call, "function", None), "name", None)
            raw_arguments = getattr(getattr(tool_call, "function", None), "arguments", "") or "{}"
            if not function_name:
                continue

            function_to_call = tool_functions.get(function_name)
            try:
                function_args = json.loads(raw_arguments)
                if not isinstance(function_args, dict):
                    function_args = {}
            except Exception:
                function_args = {}

            if function_to_call:
                try:
                    logger.info("Executing xAI tool '%s' with args: %s", function_name, function_args)
                    tool_output = function_to_call(**function_args)
                except Exception as tool_error:
                    logger.error("Error executing xAI tool %s: %s", function_name, tool_error)
                    tool_output = f"Error: {tool_error}"
            else:
                tool_output = f"Error: Tool '{function_name}' not found."

            chat.append(
                xai_tool_result(
                    self._tool_result_payload(tool_output),
                    tool_call_id=getattr(tool_call, "id", None),
                )
            )

    async def _sample_chat(self, chat: Any) -> Tuple[str, Optional[Dict[str, int]], Any]:
        response = await chat.sample()
        return response.content or "", xai_sampling_usage_to_dict(response.usage), response

    async def get_response_stream(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None,
    ) -> AsyncGenerator[Tuple[str, Union[str, Dict[str, int]]], None]:
        try:
            prepared_messages = self._prepare_messages(messages, images)
            if not prepared_messages:
                yield "final", self._handle_error(Exception("No valid message content to send."))
                return

            prepared_tools = self._prepare_tools(tools) if tools and tool_functions else None
            chat = self.client.chat.create(**self._chat_kwargs(prepared_messages, prepared_tools))

            usage_data: Optional[Dict[str, int]] = None
            if prepared_tools and tool_functions:
                first_text, first_usage, first_response = await self._sample_chat(chat)
                usage_data = self._merge_usage(usage_data, first_usage)

                if first_response.tool_calls:
                    self._append_tool_results(chat, first_response, tool_functions)
                else:
                    yield "final", first_text
                    if usage_data:
                        yield "usage", usage_data
                    return

            if self.stream:
                final_response = None
                async for streamed_response, chunk in chat.stream():
                    final_response = streamed_response
                    if chunk.content:
                        yield "partial", streamed_response.content

                final_text = final_response.content if final_response else ""
                yield "final", final_text

                final_usage = xai_sampling_usage_to_dict(final_response.usage) if final_response else None
                usage_data = self._merge_usage(usage_data, final_usage)
                if usage_data:
                    yield "usage", usage_data
                return

            final_text, final_usage, _ = await self._sample_chat(chat)
            yield "final", final_text

            usage_data = self._merge_usage(usage_data, final_usage)
            if usage_data:
                yield "usage", usage_data

        except Exception as e:
            yield "final", self._handle_error(e)
