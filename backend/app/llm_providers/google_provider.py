# backend/app/llm_providers/google_provider.py
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

from google import genai
from google.genai import types

from .base import LLMProvider

logger = logging.getLogger(__name__)


class GoogleProvider(LLMProvider):
    """
    LLMProvider implementation for Google's Gemini API via google-genai SDK.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = genai.Client(api_key=self.api_key)

    @staticmethod
    def _extract_text_from_response(response: Any) -> str:
        try:
            text = response.text
            if text:
                return text
        except Exception:
            pass

        output_chunks: List[str] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    output_chunks.append(part_text)
        return "".join(output_chunks)

    @staticmethod
    def _extract_usage(response: Any) -> Optional[Dict[str, int]]:
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return None
        input_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        if input_tokens is None and output_tokens is None:
            return None
        return {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
        }

    @staticmethod
    def _stringify_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
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
        self, messages: List[Dict[str, Any]], images: Optional[List[bytes]]
    ) -> Tuple[Optional[str], List[types.Content]]:
        system_prompt: Optional[str] = None
        content_list: List[types.Content] = []

        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system_prompt = self._stringify_content(msg.get("content", ""))
                continue

            message_role = "model" if role == "assistant" else "user"
            text = self._stringify_content(msg.get("content", ""))
            parts = [types.Part.from_text(text=text)] if text else []
            content_list.append(types.Content(role=message_role, parts=parts))

        if images:
            image_parts = [types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images]
            if content_list and content_list[-1].role == "user":
                content_list[-1].parts = (content_list[-1].parts or []) + image_parts
            else:
                content_list.append(types.Content(role="user", parts=image_parts))

        return system_prompt, content_list

    @staticmethod
    def _prepare_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[types.Tool]]:
        if not tools:
            return None

        declarations: List[types.FunctionDeclaration] = []
        for tool in tools:
            declaration = tool.get("function", tool)
            name = declaration.get("name")
            if not name:
                continue
            declarations.append(
                types.FunctionDeclaration(
                    name=name,
                    description=declaration.get("description"),
                    parameters_json_schema=declaration.get("parameters"),
                )
            )

        if not declarations:
            return None

        return [types.Tool(function_declarations=declarations)]

    def _prepare_generation_config(
        self,
        system_prompt: Optional[str],
        genai_tools: Optional[List[types.Tool]],
    ) -> types.GenerateContentConfig:
        custom = dict(self.custom_params)
        mapped = {
            "max_tokens": "max_output_tokens",
            "temperature": "temperature",
            "top_p": "top_p",
            "top_k": "top_k",
            "n": "candidate_count",
        }
        config_kwargs: Dict[str, Any] = {}

        for src_key, target_key in mapped.items():
            if src_key in custom:
                config_kwargs[target_key] = custom.pop(src_key)

        config_kwargs.update(custom)

        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if genai_tools:
            config_kwargs["tools"] = genai_tools
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)

        return types.GenerateContentConfig(**config_kwargs)

    @staticmethod
    def _extract_function_calls(response: Any) -> List[Any]:
        function_calls = getattr(response, "function_calls", None)
        return list(function_calls or [])

    def _append_tool_call_turns(
        self, contents: List[types.Content], function_calls: List[Any], tool_functions: Dict[str, callable]
    ) -> List[types.Content]:
        model_parts: List[types.Part] = []
        tool_parts: List[types.Part] = []

        for function_call in function_calls:
            fn_name = getattr(function_call, "name", None)
            fn_args = dict(getattr(function_call, "args", {}) or {})
            if not fn_name:
                continue

            model_parts.append(types.Part.from_function_call(name=fn_name, args=fn_args))

            function_to_call = tool_functions.get(fn_name)
            if function_to_call:
                try:
                    logger.info("Executing tool '%s' with args: %s", fn_name, fn_args)
                    function_result = function_to_call(**fn_args)
                    parsed_result: Any = function_result
                    if isinstance(function_result, str):
                        try:
                            parsed_result = json.loads(function_result)
                        except Exception:
                            parsed_result = {"result": function_result}
                    elif not isinstance(function_result, dict):
                        parsed_result = {"result": function_result}

                    tool_parts.append(
                        types.Part.from_function_response(name=fn_name, response=parsed_result)
                    )
                except Exception as tool_error:
                    logger.error("Error executing tool %s: %s", fn_name, tool_error)
                    tool_parts.append(
                        types.Part.from_function_response(
                            name=fn_name, response={"error": str(tool_error)}
                        )
                    )
            else:
                tool_parts.append(
                    types.Part.from_function_response(
                        name=fn_name, response={"error": f"Tool '{fn_name}' not found."}
                    )
                )

        updated_contents = list(contents)
        if model_parts:
            updated_contents.append(types.Content(role="model", parts=model_parts))
        if tool_parts:
            updated_contents.append(types.Content(role="user", parts=tool_parts))
        return updated_contents

    async def _generate_non_stream(self, model: str, contents: List[types.Content], config: types.GenerateContentConfig) -> Any:
        return await self.client.aio.models.generate_content(model=model, contents=contents, config=config)

    async def _generate_stream(self, model: str, contents: List[types.Content], config: types.GenerateContentConfig) -> AsyncGenerator[Any, None]:
        async for chunk in self.client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            yield chunk

    async def get_response_stream(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None,
    ) -> AsyncGenerator[Tuple[str, Union[str, Dict[str, int]]], None]:
        try:
            system_prompt, contents = self._prepare_messages(messages, images)
            genai_tools = self._prepare_tools(tools)
            config = self._prepare_generation_config(system_prompt, genai_tools)

            if not contents:
                yield "final", self._handle_error(Exception("No valid message content to send."))
                return

            combined_usage: Optional[Dict[str, int]] = None

            if genai_tools and tool_functions:
                first_response = await self._generate_non_stream(self.model, contents, config)
                first_usage = self._extract_usage(first_response)
                if first_usage:
                    combined_usage = dict(first_usage)

                function_calls = self._extract_function_calls(first_response)
                if function_calls:
                    contents = self._append_tool_call_turns(contents, function_calls, tool_functions)

            if self.stream:
                full_response = ""
                latest_usage: Optional[Dict[str, int]] = None
                async for chunk in self._generate_stream(self.model, contents, config):
                    chunk_usage = self._extract_usage(chunk)
                    if chunk_usage:
                        latest_usage = chunk_usage

                    chunk_text = self._extract_text_from_response(chunk)
                    if chunk_text:
                        full_response += chunk_text
                        yield "partial", full_response

                yield "final", full_response

                final_usage = latest_usage
                if combined_usage and final_usage:
                    final_usage = {
                        "input_tokens": combined_usage["input_tokens"] + final_usage["input_tokens"],
                        "output_tokens": combined_usage["output_tokens"] + final_usage["output_tokens"],
                    }
                elif combined_usage:
                    final_usage = combined_usage

                if final_usage:
                    yield "usage", final_usage
                return

            final_response = await self._generate_non_stream(self.model, contents, config)
            final_text = self._extract_text_from_response(final_response)
            yield "final", final_text

            final_usage = self._extract_usage(final_response)
            if combined_usage and final_usage:
                final_usage = {
                    "input_tokens": combined_usage["input_tokens"] + final_usage["input_tokens"],
                    "output_tokens": combined_usage["output_tokens"] + final_usage["output_tokens"],
                }
            elif not final_usage:
                final_usage = combined_usage

            if final_usage:
                yield "usage", final_usage

        except Exception as e:
            yield "final", self._handle_error(e)
