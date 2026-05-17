import asyncio
import io
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends
from PIL import Image, ImageDraw

import openai
from google import genai
import anthropic
from xai_sdk.chat import user as xai_user

from ..dependencies import get_api_key
from ..models import AvailableModelsRequest, ModelTestRequest
from ..ocr_service import DEFAULT_OCR_PROMPT_TEMPLATE, OCR_TIMEOUT_SECONDS, extract_ocr_text, get_ocr_timeout_seconds
from ..xai_sdk_utils import (
    create_xai_sync_client,
    list_xai_embedding_model_names,
    list_xai_language_model_names,
    probe_xai_embedding,
    xai_sampling_usage_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in {"openai_compatible", "openai-compatible"}:
        return "openai"
    if normalized in {"gemini", "google"}:
        return "google"
    if normalized in {"anthropic_compatible", "anthropic-compatible"}:
        return "anthropic"
    if normalized in {"xai", "grok", "x.ai"}:
        return "grok"
    if normalized in {"deepseek", "siliconflow", "volcengine", "dashscope", "moonshot", "zhipu", "stepfun"}:
        return "openai"
    return normalized


def _list_xai_models_for_task(client, task: str) -> List[str]:
    normalized_task = (task or "chat").strip().lower()
    if normalized_task == "embedding":
        return list_xai_embedding_model_names(client)
    if normalized_task == "ocr":
        return list_xai_language_model_names(client, image_capable_only=True)
    return list_xai_language_model_names(client)


def _build_ocr_test_image_bytes() -> bytes:
    image = Image.new("RGB", (320, 120), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 35), "OCR TEST 2048", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _test_ocr_model_connection(request) -> Dict[str, Any]:
    ocr_test_config = {
        "ocr_provider": request.provider,
        "ocr_api_key": request.api_key,
        "ocr_base_url": request.base_url,
        "ocr_port": "",
        "ocr_model_name": request.model_name,
        "ocr_prompt_template": DEFAULT_OCR_PROMPT_TEMPLATE,
        "ocr_max_output_chars": 1200,
        "ocr_timeout_seconds": request.ocr_timeout_seconds or OCR_TIMEOUT_SECONDS,
        "ocr_timeout_disabled": request.ocr_timeout_disabled,
    }
    timeout_seconds = get_ocr_timeout_seconds(ocr_test_config)

    try:
        extraction_task = extract_ocr_text(
            [{"bytes": _build_ocr_test_image_bytes(), "label": "Connection test image"}],
            ocr_test_config,
        )
        if timeout_seconds is None:
            ocr_text, usage_data = await extraction_task
        else:
            ocr_text, usage_data = await asyncio.wait_for(extraction_task, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return {"success": False, "error": f"OCR model test timed out after {timeout_seconds} seconds."}

    if not ocr_text.strip():
        return {"success": False, "error": "OCR model returned an empty response."}
    return {"success": True, "response": ocr_text, "model_info": {"id": request.model_name, "usage": usage_data}}


@router.post("/api/models/list", dependencies=[Depends(get_api_key)])
async def get_available_models(request: AvailableModelsRequest):
    try:
        provider = _normalize_provider(request.provider)
        task = (request.task or "chat").strip().lower()

        if provider == "openai":
            client = openai.OpenAI(api_key=request.api_key, base_url=request.base_url if request.base_url else None)
            models = client.models.list()
            model_ids = sorted([m.id for m in models if getattr(m, "id", None)])
            if task == "embedding":
                model_ids = [m for m in model_ids if "embedding" in m.lower()]
            elif task == "chat":
                model_ids = [m for m in model_ids if "gpt" in m.lower() or "chat" in m.lower()]
            return {"models": sorted(model_ids, reverse=True)}

        elif provider == "grok":
            client = create_xai_sync_client(request.api_key, request.base_url)
            return {"models": _list_xai_models_for_task(client, task)}

        elif provider == "google":
            client = genai.Client(api_key=request.api_key)
            models = client.models.list()
            selected_models = []
            for model in models:
                supported_actions = getattr(model, "supported_actions", None) or []
                supports_generate = any(str(action) in {"generateContent", "generate_content"} for action in supported_actions)
                supports_embedding = any(str(action) in {"embedContent", "embed_content"} for action in supported_actions)
                supports_task = supports_embedding if task == "embedding" else supports_generate
                if supports_task and getattr(model, "name", None):
                    selected_models.append(model.name.replace('models/', ''))
            return {"models": sorted(selected_models)}

        elif provider == "anthropic":
            fallback_models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307", "claude-2.1", "claude-2.0"]
            try:
                client = anthropic.Anthropic(api_key=request.api_key, base_url=request.base_url if request.base_url else None)
                models_page = client.models.list(limit=50)
                model_ids = sorted([m.id for m in models_page.data if getattr(m, "id", None)])
                return {"models": model_ids or fallback_models}
            except Exception:
                return {"models": fallback_models}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider '{request.provider}'.")
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {str(e)}")


@router.post("/api/models/test", dependencies=[Depends(get_api_key)])
async def test_model_connection(request: ModelTestRequest):
    try:
        provider = _normalize_provider(request.provider)
        task = (request.task or "chat").strip().lower()
        test_message = "Hi, this is a connection test. Please respond with 'OK'."

        if task == "ocr":
            return await _test_ocr_model_connection(request)

        if provider == "openai":
            client = openai.OpenAI(api_key=request.api_key, base_url=request.base_url if request.base_url else None)
            if task == "rerank":
                models = client.models.list()
                model_ids = {m.id for m in models if getattr(m, "id", None)}
                if request.model_name in model_ids:
                    return {"success": True, "response": "Rerank model is available.", "model_info": {"id": request.model_name}}
                return {"success": False, "error": f"Model '{request.model_name}' was not found on this endpoint."}
            if task == "embedding":
                response = client.embeddings.create(model=request.model_name, input="connection test")
                vector_count = len(response.data[0].embedding) if response.data else 0
                return {"success": True, "response": f"Embedding generated (dimension={vector_count}).", "model_info": {"id": request.model_name, "usage": response.usage.dict() if getattr(response, "usage", None) else None}}
            response = client.chat.completions.create(model=request.model_name, messages=[{"role": "user", "content": test_message}], max_tokens=10)
            return {"success": True, "response": response.choices[0].message.content, "model_info": {"id": response.model, "usage": response.usage.dict() if response.usage else None}}

        elif provider == "grok":
            client = create_xai_sync_client(request.api_key, request.base_url)
            available_models = set(_list_xai_models_for_task(client, task))
            if task == "rerank":
                if request.model_name in available_models:
                    return {"success": True, "response": "Model is available.", "model_info": {"id": request.model_name}}
                return {"success": False, "error": f"Model '{request.model_name}' was not found on this xAI account."}
            if task == "embedding":
                vector_count, usage = probe_xai_embedding(client, request.model_name, "connection test")
                return {"success": True, "response": f"Embedding generated (dimension={vector_count}).", "model_info": {"id": request.model_name, "usage": usage}}
            chat = client.chat.create(model=request.model_name, messages=[xai_user(test_message)], max_tokens=10)
            response = chat.sample()
            return {"success": True, "response": response.content, "model_info": {"id": request.model_name, "usage": xai_sampling_usage_to_dict(response.usage)}}

        elif provider == "google":
            client = genai.Client(api_key=request.api_key)
            if task == "rerank":
                models = client.models.list()
                model_names = [str(m.name).replace("models/", "") for m in models if getattr(m, "name", None)]
                if request.model_name in set(model_names):
                    return {"success": True, "response": "Rerank model is available.", "model_info": {"id": request.model_name}}
                return {"success": False, "error": f"Model '{request.model_name}' was not found."}
            if task == "embedding":
                response = client.models.embed_content(model=request.model_name, contents="connection test")
                embedding_values = getattr(response, "embeddings", None) or []
                dim = len(embedding_values[0].values) if embedding_values and hasattr(embedding_values[0], "values") else 0
                return {"success": True, "response": f"Embedding generated (dimension={dim}).", "model_info": {"id": request.model_name}}
            response = client.models.generate_content(model=request.model_name, contents=test_message)
            response_text = response.text or ""
            if not response_text and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    response_text = "".join(part.text or "" for part in candidate.content.parts)
            return {"success": True, "response": response_text, "model_info": {"id": request.model_name}}

        elif provider == "anthropic":
            if task == "rerank":
                try:
                    client = anthropic.Anthropic(api_key=request.api_key, base_url=request.base_url if request.base_url else None)
                    models_page = client.models.list(limit=50)
                    model_ids = {m.id for m in models_page.data if getattr(m, "id", None)}
                    if request.model_name in model_ids:
                        return {"success": True, "response": "Rerank model is available.", "model_info": {"id": request.model_name}}
                    return {"success": False, "error": f"Model '{request.model_name}' was not found."}
                except Exception:
                    return {"success": False, "error": "Unable to verify rerank model list."}
            if task == "embedding":
                return {"success": False, "error": "Embedding test is not supported for Anthropic."}
            client = anthropic.Anthropic(api_key=request.api_key, base_url=request.base_url if request.base_url else None)
            response = client.messages.create(model=request.model_name, max_tokens=10, messages=[{"role": "user", "content": test_message}])
            return {"success": True, "response": response.content[0].text, "model_info": {"id": response.model}}
        else:
            return {"success": False, "error": f"Unsupported provider '{request.provider}'."}
    except Exception as e:
        logger.error(f"Model test failed: {e}", exc_info=True)
        return {"success": False, "error": "Model test failed. Check backend logs for details."}
