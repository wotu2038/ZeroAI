"""
组合管理API

提供组合的创建、查询、更新、删除功能
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging
from app.services.composite_service import CompositeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/composite", tags=["组合管理"])


# 请求模型
class CompositeCreate(BaseModel):
    name: str
    type: str  # project, feature, document, custom
    description: Optional[str] = None
    group_ids: List[str] = []


class CompositeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    group_ids: Optional[List[str]] = None


# 响应模型
class CompositeResponse(BaseModel):
    uuid: str
    name: str
    type: str
    description: Optional[str] = None
    group_ids: List[str] = []
    created_at: str
    updated_at: Optional[str] = None


@router.post("/create", response_model=CompositeResponse)
async def create_composite(composite: CompositeCreate):
    """
    创建组合
    
    将多个GroupID关联在一起，形成项目、功能等业务概念
    """
    try:
        result = CompositeService.create_composite(
            name=composite.name,
            composite_type=composite.type,
            description=composite.description,
            group_ids=composite.group_ids
        )
        return CompositeResponse(**result)
    except Exception as e:
        logger.error(f"创建组合失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/list", response_model=List[CompositeResponse])
async def list_composites(
    type: Optional[str] = Query(None, description="组合类型筛选")
):
    """
    获取组合列表
    
    支持按类型筛选
    """
    try:
        composites = CompositeService.list_composites(composite_type=type)
        return [CompositeResponse(**c) for c in composites]
    except Exception as e:
        logger.error(f"获取组合列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/{composite_uuid}", response_model=CompositeResponse)
async def get_composite(composite_uuid: str):
    """
    获取组合详情
    """
    try:
        composite = CompositeService.get_composite(composite_uuid)
        if not composite:
            raise HTTPException(status_code=404, detail="组合不存在")
        return CompositeResponse(**composite)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取组合详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.put("/{composite_uuid}", response_model=CompositeResponse)
async def update_composite(composite_uuid: str, composite: CompositeUpdate):
    """
    更新组合
    
    可以更新名称、描述和关联的GroupID列表
    """
    try:
        result = CompositeService.update_composite(
            composite_uuid=composite_uuid,
            name=composite.name,
            description=composite.description,
            group_ids=composite.group_ids
        )
        if not result:
            raise HTTPException(status_code=404, detail="组合不存在")
        return CompositeResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新组合失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{composite_uuid}")
async def delete_composite(composite_uuid: str):
    """
    删除组合
    
    只删除组合节点和关联关系，不影响原始GroupID的数据
    """
    try:
        success = CompositeService.delete_composite(composite_uuid)
        if not success:
            raise HTTPException(status_code=404, detail="组合不存在")
        return {"message": "删除成功", "uuid": composite_uuid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除组合失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/{composite_uuid}/graph", response_model=Dict[str, Any])
async def get_composite_graph(
    composite_uuid: str,
    limit: int = Query(2000, ge=1, le=5000, description="返回节点数量限制")
):
    """
    获取组合的图谱数据
    
    合并所有关联GroupID的节点和关系，每个节点/关系都标记了来源GroupID
    """
    try:
        result = CompositeService.get_composite_graph(composite_uuid, limit=limit)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取组合图谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")

