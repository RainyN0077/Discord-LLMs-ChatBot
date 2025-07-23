# backend/app/llm_providers/google_provider.py
import google.generativeai as genai
import PIL.Image
import io
import json
import logging
from typing import Any, Dict, List, AsyncGenerator, Tuple, Optional

from .base import LLMProvider
import google.generativeai.types as genai_types
from google.ai.generativelanguage import Part, FunctionResponse, Type

logger = logging.getLogger(__name__)

class GoogleProvider(LLMProvider):
    """
    LLMProvider implementation for Google's Gemini API.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        genai.configure(api_key=self.api_key)
        self.model_instance = genai.GenerativeModel(self.model)

    def _prepare_request_params(self) -> Dict[str, Any]:
        """
        Maps standard parameters to Google-specific generation config.
        """
        generation_config_params = {}
        if "max_tokens" in self.custom_params:
            generation_config_params["max_output_tokens"] = self.custom_params.pop("max_tokens")
        if "temperature" in self.custom_params:
            generation_config_params["temperature"] = self.custom_params.pop("temperature")
        if "top_p" in self.custom_params:
            generation_config_params["top_p"] = self.custom_params.pop("top_p")
        # Google's API uses 'candidate_count' instead of 'n', and 'top_k' is supported.
        # We will map them if they exist in custom_params.
        if "top_k" in self.custom_params:
             generation_config_params["top_k"] = self.custom_params.pop("top_k")
        
        api_kwargs = {}
        if generation_config_params:
            api_kwargs['generation_config'] = genai.types.GenerationConfig(**generation_config_params)
        
        # Add any remaining custom params that might be supported directly
        api_kwargs.update(self.custom_params)
        return api_kwargs

    def _prepare_messages(self, messages: List[Dict[str, Any]], images: Optional[List[bytes]]) -> List[Any]:
        """
        Formats messages for the Gemini API, handling multi-modal content.
        The format is a list containing strings and PIL.Image objects.
        """
        # Google's format is a flat list of content parts.
        # We will simulate the conversation history as a single prompt block.
        prompt_parts = []
        for msg in messages:
            # The 'system' role is not explicitly supported in the same way. 
            # It's usually prepended to the user's first message.
            # For simplicity, we treat system, user, and assistant messages as part of a continuous conversation script.
            role_prefix = f"{msg['role'].capitalize()}: "
            prompt_parts.append(f"{role_prefix}{msg['content']}")
        
        prompt = "\n\n".join(prompt_parts)
        
        generation_input = [prompt]
        if images:
            for img_bytes in images:
                img = PIL.Image.open(io.BytesIO(img_bytes))
                generation_input.append(img)
                
        return generation_input

    async def get_response_stream(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[bytes]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_functions: Optional[Dict[str, callable]] = None
    ) -> AsyncGenerator[Tuple[str, str], None]:
        
        # Note: Gemini's Python SDK has some complexities with history & roles.
        # We'll stick to a simpler "single-turn" chat for now and build the history manually.
        # System prompt is prepended to the first user message.
        history_for_gemini = []
        system_prompt = None
        if messages and messages[0]['role'] == 'system':
            system_prompt = messages[0]['content']
            messages = messages[1:]

        for msg in messages:
            role = 'user' if msg['role'] == 'user' else 'model'
            # For now, we will merge content into a single string for simplicity.
            # A more advanced implementation would handle complex content arrays.
            content_text = msg['content'] if isinstance(msg['content'], str) else str(msg['content'])
            if msg['role'] == 'user' and system_prompt:
                content_text = f"{system_prompt}\n\n{content_text}"
                system_prompt = None # Only use it once
            history_for_gemini.append({'role': role, 'parts': [content_text]})

        # The last message is the one we send now.
        # The history needs to be passed to `start_chat`.
        current_message_parts = history_for_gemini.pop()['parts']

        if images:
            for img_bytes in images:
                img = PIL.Image.open(io.BytesIO(img_bytes))
                current_message_parts.append(img)
        
        api_kwargs = self._prepare_request_params()
        
        try:
            chat = self.model_instance.start_chat(
                history=history_for_gemini,
            )
            
            # Add tools if available.
            sanitized_tools = None
            if tools:
                # [FIX] Deeply convert OpenAI-style tool schemas to Google's format.
                # This involves both removing the top-level 'type: object' from parameters
                # and converting type strings (e.g., "string") to Google's Type enum.
                
                # Mapping from JSON Schema types to Google's Type enum
                type_map = {
                    "string": Type.STRING,
                    "number": Type.NUMBER,
                    "integer": Type.INTEGER,
                    "boolean": Type.BOOLEAN,
                    "array": Type.ARRAY,
                    "object": Type.OBJECT,
                }

                def _convert_schema(schema_dict):
                    if not isinstance(schema_dict, dict):
                        return schema_dict
                    
                    # Recursively convert nested properties first
                    if 'properties' in schema_dict:
                        for key, prop in schema_dict['properties'].items():
                            schema_dict['properties'][key] = _convert_schema(prop)
                    
                    # Convert items in arrays
                    if 'items' in schema_dict:
                        schema_dict['items'] = _convert_schema(schema_dict['items'])
                        
                    # Convert the type string to enum at the current level
                    if 'type' in schema_dict and schema_dict['type'] in type_map:
                        schema_dict['type'] = type_map[schema_dict['type']]
                        
                    return schema_dict

                sanitized_tools = []
                tools_copy = json.loads(json.dumps(tools)) # Deep copy

                for tool_def in tools_copy:
                    declaration = tool_def.get('function', tool_def)
                    
                    if 'parameters' in declaration:
                        # Recursively convert all type strings to enums
                        declaration['parameters'] = _convert_schema(declaration['parameters'])
                        
                    sanitized_tools.append(declaration)

            response = await chat.send_message_async(
                current_message_parts,
                stream=self.stream,
                generation_config=api_kwargs.get('generation_config'),
                tools=sanitized_tools
            )

            if self.stream:
                full_response = ""
                # Streaming with tools is complex; we'll collect the response first.
                # This is a limitation of the current SDK state.
                collected_chunks = [chunk async for chunk in response]
                
                # Check for tool calls in the collected response
                tool_call_chunks = [chunk for chunk in collected_chunks if chunk.parts and chunk.parts[0].function_call]
                if tool_call_chunks and tool_functions:
                    function_call = tool_call_chunks[0].parts[0].function_call
                    function_name = function_call.name
                    function_to_call = tool_functions.get(function_name)
                    
                    if function_to_call:
                        try:
                            # Gemini provides args as a dict-like object
                            function_args = dict(function_call.args)
                            logger.info(f"Executing tool '{function_name}' with args: {function_args}")
                            function_response = function_to_call(**function_args)
                            
                            # Send the tool response back to the model
                            tool_response_part = Part(
                                function_response=FunctionResponse(
                                    name=function_name,
                                    response={'result': function_response}
                                )
                            )
                            second_response = await chat.send_message_async(tool_response_part)
                            yield "final", second_response.text
                            return
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {e}")
                            yield "final", f"Error executing tool: {e}"
                            return
                
                # If no tool calls, process as regular text stream
                for chunk in collected_chunks:
                    try:
                        # [FIX] Check for safety feedback before accessing text
                        if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                            reason = chunk.prompt_feedback.block_reason.name
                            ratings = [str(rating) for rating in chunk.prompt_feedback.safety_ratings]
                            error_msg = f"Response blocked by Google's safety settings. Reason: {reason}. Details: {', '.join(ratings)}"
                            logger.warning(error_msg)
                            full_response += f" [SYSTEM: {error_msg}]"
                            break # Stop processing further chunks
                        
                        if chunk.text:
                            full_response += chunk.text
                            yield "partial", full_response
                    except ValueError:
                        # This can happen if the chunk is empty (e.g. safety stop)
                        logger.warning("Encountered an empty chunk from Google API, possibly due to safety settings.")
                        pass
                yield "final", full_response

            else: # Non-streaming mode
                # [FIX] Check for safety feedback before accessing text
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason.name
                    ratings = [str(rating) for rating in response.prompt_feedback.safety_ratings]
                    error_msg = f"Response blocked by Google's safety settings. Reason: {reason}. Details: {', '.join(ratings)}"
                    logger.warning(error_msg)
                    yield "final", self._handle_error(Exception(error_msg))
                    return

                if response.parts and response.parts[0].function_call and tool_functions:
                    function_call = response.parts[0].function_call
                    function_name = function_call.name
                    function_to_call = tool_functions.get(function_name)
                    
                    if function_to_call:
                        try:
                            function_args = dict(function_call.args)
                            logger.info(f"Executing tool '{function_name}' with args: {function_args}")
                            function_response = function_to_call(**function_args)
                            
                            tool_response_part = Part(
                                function_response=FunctionResponse(
                                    name=function_name,
                                    response={'result': function_response}
                                )
                            )
                            second_response = await chat.send_message_async(tool_response_part)
                            yield "final", second_response.text
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {e}")
                            yield "final", f"Error executing tool: {e}"
                    else:
                        yield "final", f"Tool '{function_name}' not found."
                else:
                    yield "final", response.text
                
        except Exception as e:
            yield "final", self._handle_error(e)