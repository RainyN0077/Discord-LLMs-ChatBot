from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from xai_sdk import AsyncClient as XAIAsyncClient
from xai_sdk import Client as XAISyncClient
from xai_sdk.proto import embed_pb2, embed_pb2_grpc, models_pb2

DEFAULT_XAI_API_HOST = "api.x.ai"


def build_xai_api_host(base_url: Optional[str]) -> str:
    cleaned = str(base_url or "").strip()
    if not cleaned:
        return DEFAULT_XAI_API_HOST

    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    host = (parsed.netloc or parsed.path.split("/")[0]).strip()
    return host or DEFAULT_XAI_API_HOST


def create_xai_sync_client(
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> XAISyncClient:
    kwargs: Dict[str, Any] = {"api_key": api_key}
    host = build_xai_api_host(base_url)
    if host:
        kwargs["api_host"] = host
    if timeout is not None:
        kwargs["timeout"] = timeout
    return XAISyncClient(**kwargs)


def create_xai_async_client(
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> XAIAsyncClient:
    kwargs: Dict[str, Any] = {"api_key": api_key}
    host = build_xai_api_host(base_url)
    if host:
        kwargs["api_host"] = host
    if timeout is not None:
        kwargs["timeout"] = timeout
    return XAIAsyncClient(**kwargs)


def xai_sampling_usage_to_dict(usage: Any) -> Optional[Dict[str, int]]:
    if not usage:
        return None

    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if prompt_tokens is None and completion_tokens is None:
        return None

    return {
        "input_tokens": int(prompt_tokens or 0),
        "output_tokens": int(completion_tokens or 0),
    }


def xai_embedding_usage_to_dict(usage: Any) -> Optional[Dict[str, int]]:
    if not usage:
        return None

    text_embeddings = getattr(usage, "num_text_embeddings", None)
    image_embeddings = getattr(usage, "num_image_embeddings", None)
    if text_embeddings is None and image_embeddings is None:
        return None

    return {
        "num_text_embeddings": int(text_embeddings or 0),
        "num_image_embeddings": int(image_embeddings or 0),
    }


def _model_name(model: Any) -> str:
    return str(getattr(model, "name", "") or "").strip()


def _supports_image_input(model: Any) -> bool:
    input_modalities = list(getattr(model, "input_modalities", None) or [])
    return models_pb2.IMAGE in input_modalities


def list_xai_language_model_names(
    client: XAISyncClient,
    *,
    image_capable_only: bool = False,
) -> List[str]:
    names: List[str] = []
    for model in client.models.list_language_models():
        if image_capable_only and not _supports_image_input(model):
            continue
        name = _model_name(model)
        if name:
            names.append(name)
    return sorted(set(names))


def list_xai_embedding_model_names(client: XAISyncClient) -> List[str]:
    names: List[str] = []
    for model in client.models.list_embedding_models():
        name = _model_name(model)
        if name:
            names.append(name)
    return sorted(set(names))


def probe_xai_embedding(
    client: XAISyncClient,
    model_name: str,
    text: str = "connection test",
) -> Tuple[int, Optional[Dict[str, int]]]:
    stub = embed_pb2_grpc.EmbedderStub(client._api_channel)
    response = stub.Embed(
        embed_pb2.EmbedRequest(
            input=[embed_pb2.EmbedInput(string=text)],
            model=model_name,
            encoding_format=embed_pb2.FORMAT_FLOAT,
        )
    )

    vector_dim = 0
    if response.embeddings and response.embeddings[0].embeddings:
        vector_dim = len(response.embeddings[0].embeddings[0].float_array)

    return vector_dim, xai_embedding_usage_to_dict(response.usage)
