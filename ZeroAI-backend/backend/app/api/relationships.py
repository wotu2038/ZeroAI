from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.schemas import Relationship, RelationshipCreate, RelationshipUpdate
from app.services.relationship_service import RelationshipService

router = APIRouter()


@router.post("", response_model=Relationship, status_code=201)
async def create_relationship(relationship: RelationshipCreate):
    """创建关系"""
    try:
        return RelationshipService.create_relationship(relationship)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[Relationship])
async def list_relationships(
    type: Optional[str] = Query(None, description="关系类型过滤"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """列出关系"""
    return RelationshipService.list_relationships(rel_type=type, limit=limit, skip=skip)


@router.get("/types", response_model=List[str])
async def get_relationship_types():
    """获取所有关系类型"""
    return RelationshipService.RELATIONSHIP_TYPES


@router.get("/entity/{entity_id}", response_model=List[Relationship])
async def get_entity_relationships(entity_id: str):
    """获取实体的所有关系"""
    return RelationshipService.get_entity_relationships(entity_id)


@router.get("/{rel_id}", response_model=Relationship)
async def get_relationship(rel_id: str):
    """获取关系"""
    relationship = RelationshipService.get_relationship(rel_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="关系不存在")
    return relationship


@router.put("/{rel_id}", response_model=Relationship)
async def update_relationship(rel_id: str, update: RelationshipUpdate):
    """更新关系"""
    relationship = RelationshipService.update_relationship(rel_id, update)
    if not relationship:
        raise HTTPException(status_code=404, detail="关系不存在")
    return relationship


@router.delete("/{rel_id}", status_code=204)
async def delete_relationship(rel_id: str):
    """删除关系"""
    success = RelationshipService.delete_relationship(rel_id)
    if not success:
        raise HTTPException(status_code=404, detail="关系不存在")
    return None

