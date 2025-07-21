# backend/app/lll_providers/openai_provider.py
import openai
import base64
import json
import logging
from typing import Any, Dict, List, AsyncGenerator, Tuple, Optional, Union

from .base import LLMProvider

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """
    LLMProvider implementation for OpenAI's API.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _prepare_messages(self, messages: List[Dict[str, Any]], images: Optional[List[bytes]]) -> List[Dict[str, Any]]:
        """
        Formats messages for the OpenAI API, handling multi-modal content.
        """
        if not images:
            return messages

        prepared_messages = messages.copy()
        last_message = prepared_messages[-1]
        
        content = [{"type": "text", "text": str(last_message.get("content", ""))}]
        
        for img_bytes in images:
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })
            
        prepared_messages[-1] = {"role": last_message["role"], "content": content}
        return prepared_messages

    async def get_response_stream(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None
    ) -> AsyncGenerator[Tuple[str, Union[str, Dict[str, int]]], None]:
        
        llm_messages = self._prepare_messages(messages, images)
        api_kwargs = {
            "model": self.model,
            "messages": llm_messages,
            "stream": self.stream,
            **self.custom_params
        }
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**api_kwargs)
            
            if self.stream:
                full_response = ""
                tool_calls = []
                full_response = ""
                tool_calls = []
                usage = None # Initialize usage
                
                async for chunk in response:
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage = chunk.usage
                    
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            full_response += delta.content
                            yield "partial", full_response
                        
                        if delta and delta.tool_calls:
                            for tool_call_chunk in delta.tool_calls:
                                if len(tool_calls) <= tool_call_chunk.index:
                                    tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                tc = tool_calls[tool_call_chunk.index]
                                if tool_call_chunk.id: tc["id"] = tool_call_chunk.id
                                if tool_call_chunk.function.name: tc["function"]["name"] = tool_call_chunk.function.name
                                if tool_call_chunk.function.arguments: tc["function"]["arguments"] += tool_call_chunk.function.arguments
                
                yield "final", full_response

                if usage:
                    yield "usage", {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens}

                if tool_calls and tool_functions:
                    llm_messages.append({ "role": "assistant", "tool_calls": tool_calls })
                    
                    for tool_call in tool_calls:
                        function_name = tool_call['function']['name']
                        function_to_call = tool_functions.get(function_name)
                        try:
                            function_args = json.loads(tool_call['function']['arguments'])
                            function_response = function_to_call(**function_args)
                            llm_messages.append({ "tool_call_id": tool_call['id'], "role": "tool", "name": function_name, "content": function_response })
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {e}")
                            llm_messages.append({ "tool_call_id": tool_call['id'], "role": "tool", "name": function_name, "content": f"Error: {e}" })
                    
                    api_kwargs["messages"] = llm_messages
                    api_kwargs["stream"] = False
                    
                    second_response = await self.client.chat.completions.create(**api_kwargs)
                    content = second_response.choices[0].message.content
                    yield "final", content if content else ""
                    
                    if second_response.usage:
                        # Combine usage data from both calls
                        total_input = (usage.prompt_tokens if usage else 0) + second_response.usage.prompt_tokens
                        total_output = (usage.completion_tokens if usage else 0) + second_response.usage.completion_tokens
                        yield "usage", {"input_tokens": total_input, "output_tokens": total_output}
                    return

            else: # Non-streaming mode
                response_message = response.choices[0].message
                total_usage = response.usage

                if response_message.tool_calls and tool_functions:
                    llm_messages.append(response_message)
                    
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        function_to_call = tool_functions.get(function_name)
                        try:
                            function_args = json.loads(tool_call.function.arguments)
                            function_response = function_to_call(**function_args)
                            llm_messages.append({ "tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": function_response })
                        except Exception as e:
                             llm_messages.append({ "tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": f"Error: {e}"})

                    second_response = await self.client.chat.completions.create(model=self.model, messages=llm_messages, stream=False, **self.custom_params)
                    content = second_response.choices[0].message.content
                    yield "final", content if content else ""
                    
                    if second_response.usage:
                        total_usage.prompt_tokens += second_response.usage.prompt_tokens
                        total_usage.completion_tokens += second_response.usage.completion_tokens
                else:
                    content = response_message.content
                    yield "final", content if content else ""

                if total_usage:
                    yield "usage", {"input_tokens": total_usage.prompt_tokens, "output_tokens": total_usage.completion_tokens}

        except Exception as e:
            yield "final", self._handle_error(e)