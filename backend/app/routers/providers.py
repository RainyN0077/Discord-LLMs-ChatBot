"""Provider 管理 REST API (Wave 4, 1.3.6).

提供 Bot 的 LLM Provider 列表查看和动态切换功能。

关键审计修复:
- P0-2: 两阶段提交 + 回滚机制
- P0-6: 路由器认证 (Depends(get_api_key))
- P1-4: 健康检查并行执行 + 独立超时 (10 秒)
- P1-6: ProviderSwitchRequest Pydantic 约束
"""

import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_api_key
from ..llm_providers.factory import PROVIDER_MAP, get_provider_pool
from ..models import (
    ProviderInfo,
    ProviderListResponse,
    ProviderSwitchRequest,
    ProviderSwitchResponse,
)
from .. import state

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/bots/{bot_id}/providers",
    tags=["providers"],
    dependencies=[Depends(get_api_key)],  # P0-6 修复
)

# ---------------------------------------------------------------------------
# 速率限制 (Sec LOW)
# ---------------------------------------------------------------------------
_last_switch_time: Dict[str, datetime] = {}
MIN_SWITCH_INTERVAL = 30  # 每 Bot 每 30 秒最多切换一次

# P1-C: 并发切换锁 — 对每个 bot_id 序列化切换操作
_switch_locks: Dict[str, asyncio.Lock] = {}


def _get_switch_lock(bot_id: str) -> asyncio.Lock:
    """获取或创建 bot_id 对应的 switch lock."""
    if bot_id not in _switch_locks:
        _switch_locks[bot_id] = asyncio.Lock()
    return _switch_locks[bot_id]


def _sanitize_provider_error(error_msg: str) -> str:
    """对 Provider 错误消息做 sanitize，只返回通用错误分类.

    P1-D: 防止将 API key、完整 error stack 等敏感信息泄露给客户端.
    """
    if not error_msg:
        return "Unknown error"
    lower = error_msg.lower()
    if "401" in error_msg or "unauthorized" in lower or "invalid" in lower and ("key" in lower or "api" in lower or "token" in lower):
        return "Authentication failed (invalid API key)"
    if "402" in error_msg or "insufficient" in lower or "limit" in lower or "quota" in lower or "billing" in lower:
        return "Insufficient quota or billing issue"
    if "403" in error_msg or "forbidden" in lower or "not allowed" in lower:
        return "Access forbidden"
    if "404" in error_msg or "not found" in lower or "model not found" in lower:
        return "Resource not found (check model name or endpoint)"
    if "429" in error_msg or "rate" in lower and "limit" in lower or "too many" in lower:
        return "Rate limited - too many requests"
    if "timeout" in lower or "timed out" in lower:
        return "Provider timed out"
    if "connection" in lower or "dns" in lower or "resolve" in lower or "refused" in lower:
        return "Connection to provider failed"
    # 通用安全分类
    return "Provider error (please check configuration)"


def _get_manager():
    """获取 BotManager 实例."""
    mgr = state.bot_manager
    if mgr is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    return mgr


def _resolve_bot_id(bot_id: str):
    """解析 bot_id 返回 (manager, instance)."""
    mgr = _get_manager()
    instance = mgr.get(bot_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return mgr, instance


def _get_known_providers() -> List[str]:
    """返回所有已知的 LLM provider 名称列表."""
    return list(PROVIDER_MAP.keys())


def _build_test_config(
    config: Dict[str, Any],
    provider_name: str,
    model_name: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """为一个 provider 构建测试用配置字典.

    Args:
        config: Bot 原始配置
        provider_name: 要测试的 provider 名称
        model_name: 模型名称
        api_key: API key
        base_url: 可选 base URL 覆盖

    Returns:
        新的配置字典 (不修改原始配置)
    """
    test_config = copy.deepcopy(config)
    test_config["llm_provider"] = provider_name
    test_config["model_name"] = model_name
    test_config["api_key"] = api_key
    if base_url:
        # 根据 provider 类型设置对应的 base_url 字段
        test_config["base_url"] = base_url
        test_config[f"{provider_name}_base_url"] = base_url
    return test_config


# ---------------------------------------------------------------------------
# GET / — 获取 Provider 列表和健康状态
# ---------------------------------------------------------------------------


@router.get("/", response_model=ProviderListResponse)
async def list_providers(bot_id: str):
    """获取 Bot 的 Provider 列表和健康状态.

    并行检查所有已配置 Provider 的健康状态，每个检查独立超时 10 秒。
    使用健康检查缓存（非 force），避免每次页面加载都触发真实 LLM ping（MEDIUM-1a）。
    """
    mgr, instance = _resolve_bot_id(bot_id)
    config: Dict[str, Any] = instance.config or {}

    current_provider = config.get("llm_provider", "openai")
    current_model = config.get("model_name", "")
    api_key = config.get("api_key", "")
    all_providers = _get_known_providers()

    # 为每个 provider 构建测试信息
    provider_configs: List[Dict[str, Any]] = []
    for provider_name in all_providers:
        is_current = provider_name == current_provider
        # 判断是否有 API key (非空即视为已配置)
        has_key = bool(api_key)
        provider_configs.append({
            "name": provider_name,
            "model": current_model if is_current else "",
            "configured": has_key,
            "is_current": is_current,
            "test_config": _build_test_config(
                config,
                provider_name,
                current_model if is_current else "",
                api_key,
            ) if has_key else None,
        })

    # P1-4 修复：并行执行健康检查，每个独立超时 10 秒
    async def _check_one(pc: Dict[str, Any]) -> ProviderInfo:
        if not pc["configured"] or pc["test_config"] is None:
            return ProviderInfo(
                name=pc["name"],
                model=pc["model"],
                healthy=None,
                latency_ms=None,
                configured=pc["configured"],
                is_current=pc["is_current"],
            )
        try:
            pool = get_provider_pool()
            # MEDIUM-1a: 列表页利用缓存（非 force），300s 内不重复真实 ping；
            # 切换路径仍使用 force=True 主动验证目标 Provider
            health = await asyncio.wait_for(
                pool.check_provider_health(pc["test_config"]),
                timeout=10.0,
            )
            return ProviderInfo(
                name=pc["name"],
                model=pc["model"],
                healthy=health.get("healthy"),
                latency_ms=health.get("latency_ms"),
                configured=pc["configured"],
                is_current=pc["is_current"],
            )
        except asyncio.TimeoutError:
            return ProviderInfo(
                name=pc["name"],
                model=pc["model"],
                healthy=False,
                latency_ms=None,
                configured=pc["configured"],
                is_current=pc["is_current"],
            )
        except Exception:
            return ProviderInfo(
                name=pc["name"],
                model=pc["model"],
                healthy=False,
                latency_ms=None,
                configured=pc["configured"],
                is_current=pc["is_current"],
            )

    results: List[ProviderInfo] = await asyncio.gather(
        *[_check_one(pc) for pc in provider_configs]
    )

    return ProviderListResponse(
        current_provider=current_provider,
        current_model=current_model,
        providers=results,
    )


# ---------------------------------------------------------------------------
# POST /switch — 切换 Bot 的 LLM Provider
# ---------------------------------------------------------------------------


@router.post("/switch", response_model=ProviderSwitchResponse)
async def switch_provider(bot_id: str, request: ProviderSwitchRequest):
    """切换 Bot 的 LLM Provider.

    两阶段提交 + 回滚机制 (P0-2 修复):
      1. 速率限制检查
      2. Phase 1: 测试新 Provider 连通性
      3. Phase 2: 备份旧配置
      4. Phase 3: 写入新配置
      5. Phase 4: 重启 Bot
      6. Phase 5: 验证新 Provider 正常
      7. 失败时自动回滚
    """
    mgr, instance = _resolve_bot_id(bot_id)
    # ---- 并发锁 (P1-C: 序列化同一 bot_id 的切换操作) ----
    switch_lock = _get_switch_lock(bot_id)
    async with switch_lock:
        return await _switch_provider_impl(bot_id, request, mgr, instance)


async def _switch_provider_impl(
    bot_id: str,
    request: ProviderSwitchRequest,
    mgr: Any,
    instance: Any,
) -> ProviderSwitchResponse:
    """Provider 切换实现 (在 switch_lock 保护下执行)."""
    # ---- 速率限制检查 ----
    now = datetime.now(timezone.utc)
    if bot_id in _last_switch_time:
        elapsed = (now - _last_switch_time[bot_id]).total_seconds()
        if elapsed < MIN_SWITCH_INTERVAL:
            remaining = int(MIN_SWITCH_INTERVAL - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit: please wait {remaining}s before switching again",
            )
    _last_switch_time[bot_id] = now
    config: Dict[str, Any] = instance.config or {}
    previous_provider = str(config.get("llm_provider", ""))
    previous_model = str(config.get("model_name", ""))

    # 验证 provider 名称是否有效
    known = _get_known_providers()
    if request.provider not in known:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported provider '{request.provider}'. "
                   f"Supported providers: {', '.join(sorted(known))}",
        )

    # ---- Phase 1: 测试新 Provider 连通性 (P0-2) ----
    test_config = _build_test_config(
        config,
        request.provider,
        request.model,
        request.api_key,
        request.base_url,
    )
    try:
        pool = get_provider_pool()
        health = await asyncio.wait_for(
            pool.check_provider_health(test_config, force=True),
            timeout=10.0,
        )
        if not health.get("healthy"):
            _sanitized = _sanitize_provider_error(health.get("error", ""))
            raise HTTPException(
                status_code=422,
                detail=f"Provider '{request.provider}' connectivity test failed: {_sanitized}",
            )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=422,
            detail=f"Provider '{request.provider}' connectivity test timed out after 10s",
        )
    except HTTPException:
        raise
    except Exception as e:
        _sanitized = _sanitize_provider_error(str(e))
        raise HTTPException(
            status_code=422,
            detail=f"Provider '{request.provider}' connectivity test failed: {_sanitized}",
        )

    # ---- Phase 2: 备份旧配置 (P0-2) ----
    old_config = copy.deepcopy(config)

    # ---- Phase 3: 写入新配置 ----
    new_config = copy.deepcopy(config)
    new_config["llm_provider"] = request.provider
    new_config["model_name"] = request.model
    new_config["api_key"] = request.api_key
    if request.base_url:
        new_config["base_url"] = request.base_url
        new_config[f"{request.provider}_base_url"] = request.base_url
    instance.save_config(new_config)

    # ---- Phase 4: 重启 Bot ----
    restart_success = False
    try:
        await mgr.restart(bot_id)
        restart_success = True
    except Exception as e:
        logger.exception("Bot restart failed after provider switch for '%s'", bot_id)
        # 回滚：恢复旧配置
        instance.save_config(old_config)
        # 尝试用旧配置重启
        try:
            await mgr.restart(bot_id)
        except Exception as rollback_e:
            logger.exception("Rollback restart also failed for '%s': %s", bot_id, rollback_e)
        # Sec LOW-1: 不向客户端回显原始异常（可能含敏感信息），仅记录类型
        logger.warning(
            "Provider switch rollback for bot '%s': restart failed (%s)",
            bot_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Bot restart failed. Config rolled back.",
        )

    # ---- Phase 5: 验证新 Provider 正常 ----
    if not instance.is_running():
        logger.error(
            "Bot '%s' not running after provider switch — rolling back config",
            bot_id,
        )
        instance.save_config(old_config)
        # 尝试用旧配置重启
        try:
            await mgr.restart(bot_id)
        except Exception as rollback_e:
            logger.exception(
                "Rollback restart also failed for '%s': %s",
                bot_id,
                rollback_e,
            )
        raise HTTPException(
            status_code=500,
            detail="Bot failed to start with new provider. Config rolled back.",
        )

    status_str = instance.status.value if hasattr(instance.status, 'value') else str(instance.status)
    return ProviderSwitchResponse(
        message=(
            f"Provider switched from '{previous_provider}/{previous_model}' "
            f"to '{request.provider}/{request.model}'"
        ),
        previous_provider=previous_provider,
        current_provider=request.provider,
        current_model=request.model,
        status=status_str,
    )
