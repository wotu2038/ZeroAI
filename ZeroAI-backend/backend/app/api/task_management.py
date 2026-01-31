"""
任务管理API
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.mysql_client import get_db
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.document_upload import DocumentUpload
from app.tasks.document_processing import process_document_task
from app.utils.markdown_to_docx import markdown_to_docx

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    task_id: str
    upload_id: int
    task_type: str
    status: str
    progress: int
    current_step: Optional[str]
    total_steps: int
    completed_steps: int
    result: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    document_name: Optional[str] = None
    
    @classmethod
    def from_task_dict(cls, task_dict: dict) -> "TaskResponse":
        """从任务字典创建响应，处理 result 字段可能是字符串的情况"""
        import json
        result = task_dict.get("result")
        if isinstance(result, str):
            try:
                task_dict["result"] = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                task_dict["result"] = {"raw": result}
        return cls(**task_dict)


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int
    page: int
    page_size: int
    items: List[TaskResponse]


class TaskSubmitRequest(BaseModel):
    """任务提交请求"""
    upload_id: int
    group_id: Optional[str] = None
    version: Optional[str] = None
    version_number: Optional[str] = None
    provider: str = "local"
    max_tokens_per_section: int = 8000
    use_thinking: bool = False
    template_id: Optional[int] = None  # 实体和关系模板ID


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    status: str
    upload_id: int
    message: str


@router.post("/submit", response_model=TaskSubmitResponse)
async def submit_task(
    request: TaskSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    提交异步任务（步骤5：处理文档）
    """
    try:
        # 验证文档是否存在
        document = db.query(DocumentUpload).filter(DocumentUpload.id == request.upload_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 检查文档状态
        from app.models.document_upload import DocumentStatus
        allowed_statuses = [DocumentStatus.PARSED, DocumentStatus.CHUNKED, DocumentStatus.ERROR]
        if document.status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"文档状态不正确，需要已解析、已分块或错误状态，当前状态：{document.status.value}"
            )
        
        # 如果group_id未提供，使用文档的document_id或生成新的
        group_id = request.group_id
        version = request.version
        version_number = request.version_number
        
        if not group_id:
            if document.document_id:
                group_id = document.document_id
                # 从文件名提取版本信息
                from app.services.word_document_service import WordDocumentService
                base_name = WordDocumentService._extract_base_name(document.file_name)
                version, version_number = WordDocumentService._extract_version(document.file_name)
            else:
                # 生成新的group_id
                from app.services.word_document_service import WordDocumentService
                base_name = WordDocumentService._extract_base_name(document.file_name)
                version, version_number = WordDocumentService._extract_version(document.file_name)
                safe_base_name = WordDocumentService._sanitize_group_id(base_name)
                date_str = datetime.now().strftime('%Y%m%d')
                group_id = f"doc_{safe_base_name}_{date_str}"
                # 保存到数据库
                document.document_id = group_id
                db.commit()
        
        # 创建任务记录
        task = TaskQueue(
            task_id="",  # 稍后更新
            upload_id=request.upload_id,
            task_type=TaskType.PROCESS_DOCUMENT.value,
            status=TaskStatus.PENDING.value,
            progress=0,
            current_step="等待处理",
            total_steps=0,
            completed_steps=0
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 生成Celery任务ID（使用数据库ID）
        celery_task_id = f"task_{task.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task.task_id = celery_task_id
        db.commit()
        
        # 加载模板配置（如果提供了template_id）
        template_config = None
        if request.template_id:
            from app.models.template import EntityEdgeTemplate
            template = db.query(EntityEdgeTemplate).filter(EntityEdgeTemplate.id == request.template_id).first()
            if not template:
                raise HTTPException(status_code=404, detail="模板不存在")
            template_config = {
                "entity_types": template.entity_types,
                "edge_types": template.edge_types,
                "edge_type_map": template.edge_type_map
            }
            # 更新使用次数
            template.usage_count += 1
            db.commit()
        else:
            # 使用默认模板
            from app.models.template import EntityEdgeTemplate
            default_template = db.query(EntityEdgeTemplate).filter(
                EntityEdgeTemplate.is_default == True
            ).first()
            if default_template:
                template_config = {
                    "entity_types": default_template.entity_types,
                    "edge_types": default_template.edge_types,
                    "edge_type_map": default_template.edge_type_map
                }
                default_template.usage_count += 1
                db.commit()
        
        # 提交Celery任务
        celery_task = process_document_task.delay(
            upload_id=request.upload_id,
            group_id=group_id,
            version=version or "",
            version_number=version_number or "",
            provider=request.provider,
            max_tokens_per_section=request.max_tokens_per_section,
            use_thinking=request.use_thinking,
            template_config=template_config
        )
        
        # 更新任务ID为Celery任务ID
        task.task_id = celery_task.id
        db.commit()
        
        return TaskSubmitResponse(
            task_id=celery_task.id,
            status="pending",
            upload_id=request.upload_id,
            message="任务已提交"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"提交任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    查询任务状态
    """
    try:
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 从Celery获取最新状态（如果任务还在运行）
        # task.status现在是字符串，需要与枚举值比较
        if task.status == TaskStatus.RUNNING.value or task.status == TaskStatus.PENDING.value:
            try:
                from app.core.celery_app import celery_app
                celery_task = celery_app.AsyncResult(task_id)
                
                if celery_task.state == 'PROGRESS':
                    # 更新进度
                    meta = celery_task.info or {}
                    task.progress = meta.get('progress', task.progress) or 0
                    task.current_step = meta.get('current_step', task.current_step)
                    # 确保 completed_steps 和 total_steps 不为 None
                    completed_steps = meta.get('completed_steps')
                    if completed_steps is not None:
                        task.completed_steps = completed_steps
                    total_steps = meta.get('total_steps')
                    if total_steps is not None:
                        task.total_steps = total_steps
                elif celery_task.state == 'SUCCESS':
                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.completed_at = datetime.now()
                    if celery_task.result:
                        task.result = celery_task.result
                elif celery_task.state == 'FAILURE':
                    task.status = TaskStatus.FAILED.value
                    task.error_message = str(celery_task.info) if celery_task.info else "任务执行失败"
                    task.completed_at = datetime.now()
                
                db.commit()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"获取Celery任务状态失败: {e}")
        
        return TaskResponse.from_task_dict(task.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"查询任务状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="任务状态筛选"),
    upload_id: Optional[int] = Query(None, description="文档ID筛选"),
    db: Session = Depends(get_db)
):
    """
    查询任务列表
    """
    try:
        query = db.query(TaskQueue)
        
        # 状态筛选
        if status:
            try:
                status_enum = TaskStatus(status)
                query = query.filter(TaskQueue.status == status_enum.value)
            except ValueError:
                pass
        
        # 文档ID筛选
        if upload_id:
            query = query.filter(TaskQueue.upload_id == upload_id)
        
        # 总数
        total = query.count()
        
        # 分页
        tasks = query.order_by(desc(TaskQueue.created_at)).offset((page - 1) * page_size).limit(page_size).all()
        
        # 获取文档信息
        items = []
        for task in tasks:
            task_dict = task.to_dict()
            # 添加文档名称
            document = db.query(DocumentUpload).filter(DocumentUpload.id == task.upload_id).first()
            if document:
                task_dict['document_name'] = document.file_name
            items.append(TaskResponse.from_task_dict(task_dict))
        
        return TaskListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"查询任务列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    取消任务
    """
    try:
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 只能取消待处理或运行中的任务
        if task.status not in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
            raise HTTPException(status_code=400, detail=f"任务状态不允许取消，当前状态：{task.status}")
        
        # 取消Celery任务
        try:
            from app.core.celery_app import celery_app
            celery_app.control.revoke(task_id, terminate=True)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"取消Celery任务失败: {e}")
        
        # 更新任务状态
        task.status = TaskStatus.CANCELLED.value
        task.completed_at = datetime.now()
        db.commit()
        
        return {"task_id": task_id, "status": "cancelled", "message": "任务已取消"}
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"取消任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")


@router.get("/{task_id}/download-docx")
async def download_task_document_docx(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    下载任务生成的文档（DOCX格式）
    """
    try:
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 检查是否是生成需求文档任务
        if task.task_type != "generate_requirement_document":
            raise HTTPException(status_code=400, detail="该任务类型不支持文档下载")
        
        # 检查任务是否完成
        if task.status != "completed":
            raise HTTPException(status_code=400, detail="任务尚未完成，无法下载文档")
        
        # 检查是否有结果
        if not task.result or not task.result.get("content"):
            raise HTTPException(status_code=404, detail="任务结果中未找到文档内容")
        
        # 获取文档内容
        content = task.result.get("content", "")
        document_name = task.result.get("document_name", "需求文档")
        
        # 转换为DOCX
        try:
            docx_bytes = markdown_to_docx(content)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Markdown转DOCX失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"文档转换失败: {str(e)}")
        
        # 返回文件
        # 对文件名进行URL编码，以支持中文文件名
        from urllib.parse import quote
        filename = f"{document_name}.docx"
        encoded_filename = quote(filename, safe='')
        
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"下载文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.post("/{task_id}/check-timeout")
async def check_and_fix_timeout_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    检查并修复超时任务
    """
    try:
        from app.core.celery_app import celery_app
        from datetime import datetime, timedelta
        
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 检查Celery任务状态
        celery_result = celery_app.AsyncResult(task_id)
        celery_state = celery_result.state
        
        # 如果任务运行超过2小时且Celery状态不是RUNNING，说明可能已超时
        if task.started_at:
            duration = datetime.now() - task.started_at
            if duration.total_seconds() > 7200:  # 2小时
                if celery_state in ['PENDING', 'REVOKED', 'FAILURE'] or celery_state is None:
                    # 更新任务状态为失败
                    task.status = TaskStatus.FAILED.value
                    task.error_message = f"任务运行超时（运行时长: {duration.total_seconds() / 3600:.2f} 小时）。Celery状态: {celery_state}"
                    task.completed_at = datetime.now()
                    db.commit()
                    return {
                        "task_id": task_id,
                        "status": "fixed",
                        "message": "任务已标记为超时失败",
                        "duration_hours": duration.total_seconds() / 3600,
                        "celery_state": celery_state
                    }
        
        return {
            "task_id": task_id,
            "status": "ok",
            "message": "任务状态正常",
            "db_status": task.status,
            "celery_state": celery_state,
            "progress": task.progress
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"检查超时任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")

