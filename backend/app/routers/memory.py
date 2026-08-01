import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Response, Depends

from ..core_logic.knowledge_manager import KnowledgeManager
from ..dependencies import get_api_key, get_knowledge_manager_dep
from ..models import (
    ClearMemoryRequest, MemoryItem, WorldBookItem, UpdateMemoryRequest,
    MemoryCandidateItem, PromoteCandidateResponse,
)
from .. import state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/memory/clear", summary="清除频道记忆", description="清除指定频道的对话记忆。设置记忆截断点，该时间点之前的记忆将被忽略。", dependencies=[Depends(get_api_key)])
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    state.MEMORY_CUTOFFS[int(request.channel_id)] = datetime.now(timezone.utc)
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}


@router.get("/api/memory", summary="获取记忆列表", description="返回知识库中所有已保存的记忆条目。", response_model=List[MemoryItem], dependencies=[Depends(get_api_key)])
async def get_all_memory_items(
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    return await km.get_all_memories()


@router.post("/api/memory", summary="添加记忆", description="手动向知识库添加一条记忆条目。支持时区转换和来源标注。", response_model=MemoryItem, dependencies=[Depends(get_api_key)])
async def add_memory_item(
    item: MemoryItem,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    try:
        utc_timestamp_str: str
        if item.timestamp and item.timezone:
            try:
                import pytz
                local_tz = pytz.timezone(item.timezone)
                naive_dt = datetime.fromisoformat(item.timestamp)
                local_dt = local_tz.localize(naive_dt)
                utc_dt = local_dt.astimezone(pytz.utc)
                utc_timestamp_str = utc_dt.isoformat()
            except (pytz.UnknownTimeZoneError, ValueError) as e:
                logger.warning(f"Could not parse timestamp '{item.timestamp}' with timezone '{item.timezone}': {e}. Falling back to now().")
                utc_timestamp_str = datetime.now(timezone.utc).isoformat()
        else:
            utc_timestamp_str = item.timestamp or datetime.now(timezone.utc).isoformat()

        user_id = item.user_id or "manual_user"
        user_name = item.user_name or "WebUI"
        source = item.source or "manual_add"

        item_id = await km.add_memory(
            content=item.content,
            timestamp=utc_timestamp_str,
            user_id=user_id,
            user_name=user_name,
            source=source,
        )

        if not item_id:
            raise HTTPException(status_code=409, detail="Memory content already exists or failed to add.")

        return {
            "id": item_id,
            "content": item.content,
            "timestamp": utc_timestamp_str,
            "user_id": user_id,
            "user_name": user_name,
            "source": source,
            "timezone": item.timezone,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add memory item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")


@router.delete("/api/memory/{item_id}", summary="删除记忆", description="按 ID 删除指定的记忆条目。", status_code=204, dependencies=[Depends(get_api_key)])
async def delete_memory_item(
    item_id: int,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    success = await km.delete_memory(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return Response(status_code=204)


@router.put("/api/memory/{item_id}", summary="更新记忆", description="更新指定记忆条目的内容。", status_code=204, dependencies=[Depends(get_api_key)])
async def update_memory_item(
    item_id: int,
    item: UpdateMemoryRequest,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    success = await km.update_memory(item_id, item.content)
    if not success:
        raise HTTPException(status_code=404, detail="Memory item not found or failed to update")
    return Response(status_code=204)


@router.get("/api/memory/candidates", summary="获取候选记忆", description="返回 LLM 自动提取但尚未确认的记忆候选条目。支持分页和包含已提升条目。", response_model=List[MemoryCandidateItem], dependencies=[Depends(get_api_key)])
async def get_memory_candidates(
    include_promoted: bool = False,
    limit: int = 200,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    return await km.get_memory_candidates(include_promoted=include_promoted, limit=limit)


@router.post("/api/memory/candidates/{candidate_id}/promote", summary="提升候选记忆", description="将候选记忆提升为正式记忆条目，使其在对话上下文中可用。", response_model=PromoteCandidateResponse, dependencies=[Depends(get_api_key)])
async def promote_memory_candidate(
    candidate_id: int,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    memory_id = await km.promote_memory_candidate(candidate_id)
    if not memory_id:
        raise HTTPException(status_code=404, detail="Memory candidate not found or failed to promote")
    return {"candidate_id": candidate_id, "memory_id": memory_id}


@router.delete("/api/memory/candidates/{candidate_id}", summary="删除候选记忆", description="删除指定的候选记忆条目。", status_code=204, dependencies=[Depends(get_api_key)])
async def delete_memory_candidate(
    candidate_id: int,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    success = await km.delete_memory_candidate(candidate_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory candidate not found")
    return Response(status_code=204)


@router.get("/api/worldbook", summary="获取世界书列表", description="返回所有世界书（World Book）条目。世界书用于关键词触发的上下文注入。", response_model=List[WorldBookItem], dependencies=[Depends(get_api_key)])
async def get_all_worldbook_items(
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    return await km.get_all_world_book_entries()


@router.post("/api/worldbook", summary="添加世界书条目", description="创建新的世界书条目。设置关键词和关联内容，对话中匹配关键词时自动注入。", response_model=WorldBookItem, dependencies=[Depends(get_api_key)])
async def add_worldbook_item(
    item: WorldBookItem,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    try:
        item_id = await km.add_world_book_entry(
            keywords=item.keywords,
            content=item.content,
            linked_user_id=item.linked_user_id,
        )
        return {**item.dict(), "id": item_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add world book item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/worldbook/{item_id}", summary="更新世界书条目", description="更新指定世界书条目的关键词、内容和启用状态。", response_model=WorldBookItem, dependencies=[Depends(get_api_key)])
async def update_worldbook_item(
    item_id: int,
    item: WorldBookItem,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    try:
        success = await km.update_world_book_entry(
            entry_id=item_id,
            keywords=item.keywords,
            content=item.content,
            enabled=item.enabled,
            linked_user_id=item.linked_user_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail="World book item not found")
        return {**item.dict(), "id": item_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update world book item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/worldbook/{item_id}", summary="删除世界书条目", description="按 ID 删除指定的世界书条目。", status_code=204, dependencies=[Depends(get_api_key)])
async def delete_worldbook_item(
    item_id: int,
    km: KnowledgeManager = Depends(get_knowledge_manager_dep),
):
    success = await km.delete_world_book_entry(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="World book item not found")
    return Response(status_code=204)