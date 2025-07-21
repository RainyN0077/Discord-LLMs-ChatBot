# backend/app/llm_providers/anthropic_provider.py
import anthropic
import base64
import json
import logging
from typing import Any, Dict, List, AsyncGenerator, Tuple, Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)

class AnthropicProvider(LLMProvider):
    """
    LLMProvider implementation for Anthropic's Claude API.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        # Anthropic's API requires max_tokens, so we set a default if not provided.
        if "max_tokens" not in self.custom_params:
            self.custom_params["max_tokens"] = 4096

    def _prepare_messages(self, messages: List[Dict[str, Any]], images: Optional[List[bytes]]) -> List[Dict[str, Any]]:
        """
        Formats messages for the Anthropic API, handling multi-modal content.
        """
        # Anthropic does not use a 'system' role in the main messages list.
        # The system prompt is passed as a separate top-level parameter.
        # We will assume the first message is the system prompt if its role is 'system'.
        # The factory logic will need to handle this separation.
        if not images:
            return messages

        prepared_messages = messages.copy()
        last_message = prepared_messages[-1]

        content = [{"type": "text", "text": str(last_message.get("content", ""))}]
        
        for img_bytes in images:
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg", # Assuming jpeg for simplicity
                    "data": img_b64
                }
            })
            
        prepared_messages[-1] = {"role": last_message["role"], "content": content}
        return prepared_messages

    async def get_response_stream(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None
    ) -> AsyncGenerator[Tuple[str, str], None]:
        
        system_prompt = None
        if messages and messages[0]['role'] == 'system':
            system_prompt = messages[0]['content']
            llm_messages = messages[1:]
        else:
            llm_messages = messages
            
        llm_messages = self._prepare_messages(llm_messages, images)
        
        api_kwargs = {
            "model": self.model,
            "messages": llm_messages,
            **self.custom_params,
        }
        if system_prompt:
            api_kwargs["system"] = system_prompt
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = {"type": "auto"}

        try:
            if self.stream:
                # Anthropic's streaming for tool use is complex.
                # We'll use a non-streaming approach for the first call when tools are present
                # to simplify logic, then stream the final text response.
                if tools and tool_functions:
                    # Make a non-streaming call to check for tool usage
                    response = await self.client.messages.create(**api_kwargs, stream=False)
                    # Now handle the response, which might contain tool calls or text
                    async for response_type, content in self._handle_anthropic_response(response, llm_messages, api_kwargs, tool_functions, stream_final=True):
                         yield response_type, content
                    return

                # Standard text streaming if no tools are involved
                async with self.client.messages.stream(**api_kwargs) as stream:
                    full_response = ""
                    async for text in stream.text_stream:
                        full_response += text
                        yield "partial", full_response
                    yield "final", full_response
            else: # Non-streaming mode
                response = await self.client.messages.create(**api_kwargs)
                async for response_type, content in self._handle_anthropic_response(response, llm_messages, api_kwargs, tool_functions, stream_final=False):
                     yield response_type, content

        except Exception as e:
            yield "final", self._handle_error(e)

    async def _handle_anthropic_response(
        self, response, messages, api_kwargs, tool_functions, stream_final
    ) -> AsyncGenerator[Tuple[str, str], None]:
        
        stop_reason = response.stop_reason
        response_content = response.content

        if stop_reason == "tool_use" and tool_functions:
            tool_use_blocks = [block for block in response_content if block.type == 'tool_use']
            
            # Append assistant's request message
            messages.append({"role": "assistant", "content": response_content})
            
            tool_results = []
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_input = tool_use.input
                tool_call_id = tool_use.id
                
                logger.info(f"Executing tool '{tool_name}' with args: {tool_input}")
                function_to_call = tool_functions.get(tool_name)
                if function_to_call:
                    try:
                        function_response = function_to_call(**tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": str(function_response),
                        })
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": f"Error: {e}",
                            "is_error": True,
                        })
                else:
                    tool_results.append({ "type": "tool_result", "tool_use_id": tool_call_id, "content": f"Error: Tool '{tool_name}' not found."})

            # Append the tool results to the conversation
            messages.append({"role": "user", "content": tool_results})
            
            # Make the second call
            api_kwargs["messages"] = messages
            
            if stream_final:
                 async with self.client.messages.stream(**api_kwargs) as stream:
                    full_response = ""
                    async for text in stream.text_stream:
                        full_response += text
                        yield "partial", full_response
                    yield "final", full_response
            else:
                 second_response = await self.client.messages.create(**api_kwargs)
                 yield "final", second_response.content[0].text

        else: # Normal text response
            text_content = "".join([block.text for block in response_content if block.type == 'text'])
            yield "final", text_content