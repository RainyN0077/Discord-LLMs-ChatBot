import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_embedding_clients: Dict[str, Any] = {}


def _get_embedding_client(config: Dict[str, Any]) -> Any:
    import openai
    provider = config.get("embedding_provider", "openai")
    api_key = config.get("embedding_api_key") or config.get("api_key")
    base_url = config.get("embedding_base_url") or config.get("base_url")
    port = str(config.get("embedding_port", "")).strip()
    if port and base_url:
        base_url = base_url.rstrip("/") + ":" + port

    cache_key = f"{provider}:{api_key}:{base_url}"
    if cache_key in _embedding_clients:
        return _embedding_clients[cache_key]

    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
    _embedding_clients[cache_key] = client
    return client


async def get_embedding(text: str, config: Dict[str, Any]) -> Optional[List[float]]:
    if not text or not text.strip():
        return None
    try:
        client = _get_embedding_client(config)
        model = config.get("embedding_model_name", "text-embedding-3-small")
        response = await client.embeddings.create(
            model=model,
            input=text.strip(),
        )
        if response.data:
            return list(response.data[0].embedding)
        return None
    except Exception as e:
        logger.error("Failed to generate embedding: %s", e)
        return None


async def get_embeddings_batch(texts: List[str], config: Dict[str, Any]) -> List[Optional[List[float]]]:
    if not texts:
        return []
    valid_texts = [t.strip() for t in texts]
    try:
        client = _get_embedding_client(config)
        model = config.get("embedding_model_name", "text-embedding-3-small")
        response = await client.embeddings.create(
            model=model,
            input=valid_texts,
        )
        result: List[Optional[List[float]]] = []
        for i, data in enumerate(response.data):
            if data.embedding:
                result.append(list(data.embedding))
            else:
                result.append(None)
        while len(result) < len(texts):
            result.append(None)
        return result
    except Exception as e:
        logger.error("Failed to generate batch embeddings: %s", e)
        return [None] * len(texts)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
