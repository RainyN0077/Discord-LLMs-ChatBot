"""Prompt Studio 预设管理 + 预览转发.

预设存储为每个 Bot 独立（或全局）的 ``presets.json`` 文件，格式为
``{name: templates}``。预设名仅作为 JSON key 使用，不参与文件系统路径。

写入使用 asyncio.Lock 串行化 + 临时文件 + ``os.replace``（Windows 上
``os.replace`` 非原子，锁用于防并发覆盖）。所有 IO 均通过
``asyncio.to_thread`` 避免阻塞事件循环。
"""

import asyncio
import json
import logging
import os
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response

from ..config_cache import get_bot_dir, load_config
from ..dependencies import get_api_key
from ..models import PromptPreviewRequest
from ..paths import DataPaths

logger = logging.getLogger(__name__)

router = APIRouter()

#: 默认预设名称（半角括号，与旧前端 i18n promptStudio.preset.defaultPresetName
#: 逐字一致，不可删除/覆盖）。
DEFAULT_PRESET_NAME = "(默认)开箱即用"

#: bot_id 合法字符集（与 models.CreateBotRequest pattern 一致，防路径穿越）。
BOT_ID_PATTERN = re.compile(r'[a-z0-9_-]+')

#: 模板必需键（与旧 frontend PromptStudio.svelte 导入校验清单逐字一致）。
REQUIRED_TEMPLATE_KEYS = [
    "message_format",
    "user_request_block",
    "system_prompt_foundation_header",
    "operational_instructions",
]

#: 默认模板结构：14 键 = 4 必填（非空默认值）+ 10 可选（空串）+ operational_instructions 列表。
#: 与前端 frontend-vue/src/pages/prompt-studio/defaultTemplates.ts 同源移植，修改需同步。
DEFAULT_TEMPLATES: Dict[str, Any] = {
    # 必填（4）
    "message_format": "「{author_name}」说：\n{content}",
    "user_request_block": "<user_request>\n{parts}\n</user_request>",
    "system_prompt_foundation_header": "你是一个乐于助人的 AI 助手，请根据以下信息回答用户的问题。",
    "operational_instructions": [],
    # 可选（10）
    "image_note": "",
    "reply_context": "",
    "deleted_reply_context": "",
    "tool_context": "",
    "memory_context": "",
    "worldbook_context": "",
    "system_prompt_persona_header": "",
    "system_prompt_situation_header": "",
    "system_prompt_participants_header": "",
    "system_prompt_security_header": "",
}

_presets_lock = asyncio.Lock()


def _validate_bot_id(bot_id: Optional[str]) -> Optional[str]:
    """校验 bot_id：非空时必须匹配 [a-z0-9_-]+，否则 400（防路径穿越）.

    None/空串返回原值，走全局预设路径。
    """
    if bot_id is None or bot_id == "":
        return bot_id
    if not BOT_ID_PATTERN.fullmatch(bot_id):
        raise HTTPException(
            status_code=400,
            detail="bot_id 只能包含小写字母、数字、下划线和连字符。",
        )
    return bot_id


def _presets_path(bot_id: Optional[str]):
    """返回预设文件路径：有 bot_id 时位于该 Bot 目录，否则位于全局 DATA_DIR."""
    _validate_bot_id(bot_id)
    if bot_id:
        return get_bot_dir(bot_id) / "presets.json"
    return DataPaths.DATA_DIR / "presets.json"


async def _read_presets(bot_id: Optional[str]) -> Dict[str, Any]:
    """读取预设文件；文件不存在时返回空字典."""
    path = _presets_path(bot_id)
    if not path.exists():
        return {}

    def _read() -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    try:
        return await asyncio.to_thread(_read)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read presets file %s: %s", path, e)
        return {}


async def _write_presets(bot_id: Optional[str], presets: Dict[str, Any]) -> None:
    """原子写入预设文件（锁 + 临时文件 + os.replace）."""
    path = _presets_path(bot_id)
    tmp_path = path.with_suffix(".tmp")

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    async with _presets_lock:
        await asyncio.to_thread(_write)


def _validate_templates(templates: Any) -> None:
    """校验模板对象，不合法时抛出 400.

    校验顺序：templates 为 dict → 4 必填键存在（字符串键 strip 非空，
    operational_instructions 须为 list[str]）→ operational_instructions
    若存在须为 list[str].
    """
    if not isinstance(templates, dict):
        raise HTTPException(status_code=400, detail="templates 必须是对象。")

    missing = []
    for key in REQUIRED_TEMPLATE_KEYS:
        value = templates.get(key)
        if key == "operational_instructions":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                missing.append(key)
        elif not isinstance(value, str) or not value.strip():
            missing.append(key)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"缺少必填模板键: {', '.join(missing)}",
        )

    if "operational_instructions" in templates:
        instructions = templates["operational_instructions"]
        if not isinstance(instructions, list) or not all(
            isinstance(item, str) for item in instructions
        ):
            raise HTTPException(
                status_code=400,
                detail="operational_instructions 必须是字符串列表。",
            )


def _validate_preset_name(name: str) -> str:
    """校验预设名：非空且长度 ≤ 64；返回 strip 后的名称."""
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="预设名称不能为空。")
    if len(name) > 64:
        raise HTTPException(status_code=400, detail="预设名称不能超过 64 个字符。")
    if name == DEFAULT_PRESET_NAME:
        raise HTTPException(status_code=400, detail="默认预设不可修改。")
    return name


@router.get("/api/prompts/presets", dependencies=[Depends(get_api_key)])
async def list_prompt_presets(bot_id: Optional[str] = None):
    """列出所有预设；默认预设恒在首位（readonly=true）；文件不存在时仅返回默认项."""
    presets = await _read_presets(bot_id)
    items: List[Dict[str, Any]] = [{"name": DEFAULT_PRESET_NAME, "readonly": True}]
    items.extend({"name": name, "readonly": False} for name in sorted(presets.keys()))
    return items


@router.get("/api/prompts/presets/{name}", dependencies=[Depends(get_api_key)])
async def get_prompt_preset(name: str, bot_id: Optional[str] = None):
    """获取单个预设：默认名返回合成模板；自定义名缺失时 404."""
    if name == DEFAULT_PRESET_NAME:
        return deepcopy(DEFAULT_TEMPLATES)

    presets = await _read_presets(bot_id)
    templates = presets.get(name)
    if templates is None:
        raise HTTPException(status_code=404, detail=f"预设 '{name}' 不存在。")
    return deepcopy(templates)


@router.put("/api/prompts/presets/{name}", dependencies=[Depends(get_api_key)])
async def save_prompt_preset(name: str, templates: Dict[str, Any], bot_id: Optional[str] = None):
    """保存/覆盖自定义预设（默认预设 400）."""
    name = _validate_preset_name(name)
    _validate_templates(templates)

    presets = await _read_presets(bot_id)
    presets[name] = templates
    await _write_presets(bot_id, presets)
    logger.info("Preset '%s' saved (bot_id=%s).", name, bot_id or "global")
    return {"message": f"预设 '{name}' 保存成功。", "name": name}


@router.delete("/api/prompts/presets/{name}", dependencies=[Depends(get_api_key)])
async def delete_prompt_preset(name: str, bot_id: Optional[str] = None):
    """删除自定义预设（默认预设 400；不存在 404；成功 204）."""
    name = (name or "").strip()
    if name == DEFAULT_PRESET_NAME:
        raise HTTPException(status_code=400, detail="默认预设不可删除。")

    presets = await _read_presets(bot_id)
    if name not in presets:
        raise HTTPException(status_code=404, detail=f"预设 '{name}' 不存在。")

    del presets[name]
    await _write_presets(bot_id, presets)
    logger.info("Preset '%s' deleted (bot_id=%s).", name, bot_id or "global")
    return Response(status_code=204)


@router.post("/api/prompts/preview", dependencies=[Depends(get_api_key)])
async def preview_prompt(request: PromptPreviewRequest, bot_id: Optional[str] = None):
    """Prompt 预览：转发到 preview_builder.generate_preview（零改造）.

    提供 bot_id 时使用该 Bot 配置（不存在 404）；缺省时使用全局配置。
    """
    from ..core_logic.preview_builder import generate_preview

    if bot_id:
        from .. import state
        mgr = state.bot_manager
        if mgr is None:
            raise HTTPException(status_code=503, detail="Bot manager not initialized")
        instance = mgr.get(bot_id)
        if instance is None:
            raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' 不存在。")
        config = instance.config
    else:
        config = load_config()

    return await generate_preview(request, config)
