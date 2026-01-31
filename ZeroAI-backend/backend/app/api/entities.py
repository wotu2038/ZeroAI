from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.schemas import Entity, EntityCreate, EntityUpdate
from app.services.entity_service import EntityService

router = APIRouter()


@router.post("", response_model=Entity, status_code=201)
async def create_entity(entity: EntityCreate):
    """创建实体"""
    try:
        return EntityService.create_entity(entity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[Entity])
async def list_entities(
    type: Optional[str] = Query(None, description="实体类型过滤"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """列出实体"""
    return EntityService.list_entities(entity_type=type, limit=limit, skip=skip)


@router.get("/search", response_model=List[Entity])
async def search_entities(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, ge=1, le=100)
):
    """搜索实体"""
    return EntityService.search_entities(keyword, limit)


@router.get("/types", response_model=List[str])
async def get_entity_types():
    """获取所有实体类型"""
    return EntityService.ENTITY_TYPES


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(entity_id: str):
    """获取实体"""
    entity = EntityService.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    return entity


@router.put("/{entity_id}", response_model=Entity)
async def update_entity(entity_id: str, update: EntityUpdate):
    """更新实体"""
    entity = EntityService.update_entity(entity_id, update)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    return entity


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(entity_id: str):
    """删除实体"""
    success = EntityService.delete_entity(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="实体不存在")
    return None

