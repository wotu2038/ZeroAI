"""
模板管理API
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
import logging

from app.core.mysql_client import get_db
from app.models.template import EntityEdgeTemplate
from app.models.schemas import (
    TemplateCreate, TemplateUpdate, TemplateResponse,
    TemplateListResponse, TemplateValidateRequest, TemplateValidateResponse,
    TemplateGenerateRequest, TemplateGenerateResponse
)
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.document_upload import DocumentUpload, DocumentStatus
from app.services.template_service import TemplateService
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["模板管理"])


@router.get("", response_model=TemplateListResponse)
async def get_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="筛选分类"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db)
):
    """
    获取模板列表
    """
    try:
        query = db.query(EntityEdgeTemplate)
        
        # 分类筛选
        if category:
            query = query.filter(EntityEdgeTemplate.category == category)
        
        # 搜索
        if search:
            query = query.filter(
                or_(
                    EntityEdgeTemplate.name.like(f"%{search}%"),
                    EntityEdgeTemplate.description.like(f"%{search}%")
                )
            )
        
        # 总数
        total = query.count()
        
        # 分页
        templates = query.order_by(
            EntityEdgeTemplate.is_default.desc(),
            EntityEdgeTemplate.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        return TemplateListResponse(
            templates=[TemplateResponse(**template.to_dict()) for template in templates],
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"获取模板列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模板列表失败: {str(e)}")


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    获取模板详情
    """
    try:
        template = db.query(EntityEdgeTemplate).filter(EntityEdgeTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        return TemplateResponse(**template.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模板详情失败: {str(e)}")


@router.post("", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db)
):
    """
    创建模板
    """
    try:
        # 校验模板格式
        is_valid, errors, warnings = TemplateService.validate_template(
            template_data.entity_types,
            template_data.edge_types,
            template_data.edge_type_map
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "模板格式校验失败",
                    "errors": errors,
                    "warnings": warnings
                }
            )
        
        # 如果设置为默认模板，取消其他模板的默认状态
        if template_data.is_default:
            db.query(EntityEdgeTemplate).filter(
                EntityEdgeTemplate.is_default == True
            ).update({"is_default": False})
        
        # 创建模板
        template = EntityEdgeTemplate(
            name=template_data.name,
            description=template_data.description,
            category=template_data.category,
            entity_types=template_data.entity_types,
            edge_types=template_data.edge_types,
            edge_type_map=template_data.edge_type_map,
            is_default=template_data.is_default,
            is_system=False
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        logger.info(f"模板创建成功: {template.id} - {template.name}")
        
        return TemplateResponse(**template.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建模板失败: {str(e)}")


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    更新模板
    """
    try:
        template = db.query(EntityEdgeTemplate).filter(EntityEdgeTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        # 系统模板不可编辑
        if template.is_system:
            raise HTTPException(status_code=403, detail="系统模板不可编辑")
        
        # 准备更新数据
        update_data = template_data.dict(exclude_unset=True)
        
        # 如果更新了实体类型、关系类型或关系映射，需要校验
        if "entity_types" in update_data or "edge_types" in update_data or "edge_type_map" in update_data:
            entity_types = update_data.get("entity_types", template.entity_types)
            edge_types = update_data.get("edge_types", template.edge_types)
            edge_type_map = update_data.get("edge_type_map", template.edge_type_map)
            
            is_valid, errors, warnings = TemplateService.validate_template(
                entity_types, edge_types, edge_type_map
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "模板格式校验失败",
                        "errors": errors,
                        "warnings": warnings
                    }
                )
        
        # 如果设置为默认模板，取消其他模板的默认状态
        if update_data.get("is_default") is True:
            db.query(EntityEdgeTemplate).filter(
                EntityEdgeTemplate.id != template_id,
                EntityEdgeTemplate.is_default == True
            ).update({"is_default": False})
        
        # 更新模板
        for key, value in update_data.items():
            setattr(template, key, value)
        
        db.commit()
        db.refresh(template)
        
        logger.info(f"模板更新成功: {template.id} - {template.name}")
        
        return TemplateResponse(**template.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新模板失败: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    删除模板
    """
    try:
        template = db.query(EntityEdgeTemplate).filter(EntityEdgeTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        # 系统模板不可删除
        if template.is_system:
            raise HTTPException(status_code=403, detail="系统模板不可删除")
        
        # 默认模板不可删除
        if template.is_default:
            raise HTTPException(status_code=403, detail="默认模板不可删除，请先设置其他模板为默认")
        
        db.delete(template)
        db.commit()
        
        logger.info(f"模板删除成功: {template_id} - {template.name}")
        
        return {"message": "模板删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除模板失败: {str(e)}")


@router.post("/validate", response_model=TemplateValidateResponse)
async def validate_template(
    template_data: TemplateValidateRequest
):
    """
    校验模板格式
    """
    try:
        is_valid, errors, warnings = TemplateService.validate_template(
            template_data.entity_types,
            template_data.edge_types,
            template_data.edge_type_map
        )
        
        return TemplateValidateResponse(
            valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    except Exception as e:
        logger.error(f"校验模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"校验模板失败: {str(e)}")


@router.post("/{template_id}/set-default", response_model=TemplateResponse)
async def set_default_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    设置默认模板
    """
    try:
        template = db.query(EntityEdgeTemplate).filter(EntityEdgeTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        # 取消其他模板的默认状态
        db.query(EntityEdgeTemplate).filter(
            EntityEdgeTemplate.id != template_id,
            EntityEdgeTemplate.is_default == True
        ).update({"is_default": False})
        
        # 设置当前模板为默认
        template.is_default = True
        db.commit()
        db.refresh(template)
        
        logger.info(f"设置默认模板成功: {template.id} - {template.name}")
        
        return TemplateResponse(**template.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"设置默认模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"设置默认模板失败: {str(e)}")


@router.post("/generate-async", response_model=TemplateGenerateResponse)
async def generate_template_async(
    request: TemplateGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    LLM异步生成模板
    
    Args:
        request: 生成请求，包含文档ID和分析模式
    """
    try:
        # 验证分析模式
        if request.analysis_mode not in ["smart_segment", "full_chunk"]:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的分析模式: {request.analysis_mode}，支持的模式：smart_segment（智能分段）、full_chunk（全文分块）"
            )
        
        # 验证文档
        document = db.query(DocumentUpload).filter(DocumentUpload.id == request.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail=f"文档不存在: document_id={request.document_id}")
        
        # 检查文档状态
        if document.status not in [DocumentStatus.PARSED, DocumentStatus.CHUNKING, DocumentStatus.CHUNKED, DocumentStatus.COMPLETED]:
            raise HTTPException(
                status_code=400,
                detail=f"文档尚未解析，无法生成模板。当前状态: {document.status.value}，需要状态: parsed/chunking/chunked/completed"
            )
        
        # 检查parsed_content是否存在
        if not document.parsed_content_path:
            raise HTTPException(
                status_code=400,
                detail="文档parsed_content文件不存在，无法生成模板。请先完成文档解析。"
            )
        
        # 提交Celery任务
        from app.tasks.generate_template import generate_template_task
        celery_task = generate_template_task.delay(
            document_id=request.document_id,
            analysis_mode=request.analysis_mode,
            template_name=request.template_name,
            description=request.description,
            category=request.category
        )
        
        # 创建任务记录
        task = TaskQueue(
            task_id=celery_task.id,
            upload_id=request.document_id,
            task_type=TaskType.GENERATE_TEMPLATE.value,
            status=TaskStatus.PENDING.value,
            progress=0,
            current_step="等待处理",
            total_steps=8,
            completed_steps=0
        )
        db.add(task)
        db.commit()
        
        logger.info(f"模板生成任务已提交: task_id={celery_task.id}, document_id={request.document_id}, mode={request.analysis_mode}")
        
        return TemplateGenerateResponse(
            task_id=celery_task.id,
            status="pending",
            message="模板生成任务已提交，正在后台处理"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"提交模板生成任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")

