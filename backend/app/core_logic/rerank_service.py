import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_rerank_clients: Dict[str, Any] = {}


def _get_rerank_client(config: Dict[str, Any]) -> Any:
    import openai
    provider = config.get("rerank_provider", "openai")
    api_key = config.get("rerank_api_key") or config.get("api_key")
    base_url = config.get("rerank_base_url") or config.get("base_url")
    port = str(config.get("rerank_port", "")).strip()
    if port and base_url:
        base_url = base_url.rstrip("/") + ":" + port

    cache_key = f"{provider}:{api_key}:{base_url}"
    if cache_key in _rerank_clients:
        return _rerank_clients[cache_key]

    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
    _rerank_clients[cache_key] = client
    return client


async def rerank(
    query: str,
    documents: List[str],
    config: Dict[str, Any],
    top_n: int = 0,
) -> List[Tuple[int, float]]:
    if not query or not documents:
        return []

    try:
        client = _get_rerank_client(config)
        model = config.get("rerank_model_name", "gpt-4.1-mini")

        import aiohttp
        base_url = str(client.base_url).rstrip("/")

        api_path = config.get("rerank_api_path", "/rerank")
        if not api_path.startswith("/"):
            api_path = "/" + api_path

        payload: Dict[str, Any] = {
            "model": model,
            "query": query,
            "documents": documents,
        }
        if top_n > 0:
            payload["top_n"] = top_n

        headers = {
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}{api_path}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("Rerank API returned status %s: %s", resp.status, text[:200])
                    return []
                data = await resp.json()

        results: List[Tuple[int, float]] = []
        for item in data.get("results", []):
            idx = int(item.get("index", 0))
            score = float(item.get("relevance_score", 0.0))
            results.append((idx, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    except Exception as e:
        logger.error("Failed to rerank documents: %s", e)
        return []
