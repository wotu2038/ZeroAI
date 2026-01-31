"""
LLM生成模板任务（Celery任务）
"""
import os
import logging
from datetime import datetime
from celery import Task
from app.core.celery_app import celery_app
from app.core.mysql_client import SessionLocal
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.document_upload import DocumentUpload, DocumentStatus
from app.models.template import EntityEdgeTemplate
from app.services.template_generation_service import TemplateGenerationService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


class ProgressTask(Task):
    """支持进度更新的任务基类"""
    def update_progress(self, progress: int, current_step: str, completed_steps: int = None, total_steps: int = None):
        """更新任务进度"""
        if self.request:
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': progress,
                    'current_step': current_step,
                    'completed_steps': completed_steps,
                    'total_steps': total_steps
                }
            )


def update_task_progress(db, task_id: str, progress: int, current_step: str, completed_steps: int = None, total_steps: int = None):
    """更新数据库中的任务进度"""
    try:
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.progress = progress or 0
            task.current_step = current_step
            if completed_steps is not None:
                task.completed_steps = completed_steps
            if total_steps is not None:
                task.total_steps = total_steps
            db.commit()
    except Exception as e:
        logger.error(f"更新任务进度失败: {e}", exc_info=True)
        db.rollback()


@celery_app.task(bind=True, base=ProgressTask, name="generate_template_task")
def generate_template_task(
    self,
    document_id: int,
    analysis_mode: str,  # "smart_segment" 或 "full_chunk"
    template_name: str = None,
    description: str = None,
    category: str = "custom"
):
    """
    异步生成模板任务
    
    Args:
        self: Celery任务实例（包含task_id）
        document_id: 文档上传ID
        analysis_mode: 分析模式（smart_segment/full_chunk）
        template_name: 模板名称（可选，不提供则自动生成）
        description: 模板描述（可选）
        category: 模板分类（默认custom）
    """
    db = SessionLocal()
    task_id = self.request.id  # 从Celery任务实例获取task_id
    
    try:
        # 更新任务状态为运行中
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.now()
            db.commit()
        
        # 更新进度：初始化（5%）
        self.update_progress(5, "初始化：验证文档和参数")
        update_task_progress(db, task_id, 5, "初始化：验证文档和参数", 0, 8)
        
        # 查询文档
        document = db.query(DocumentUpload).filter(DocumentUpload.id == document_id).first()
        if not document:
            raise Exception(f"文档不存在: document_id={document_id}")
        
        # 检查文档状态
        if document.status not in [DocumentStatus.PARSED, DocumentStatus.CHUNKING, DocumentStatus.CHUNKED, DocumentStatus.COMPLETED]:
            raise Exception(f"文档尚未解析，无法生成模板。当前状态: {document.status.value}")
        
        # 检查parsed_content是否存在
        if not document.parsed_content_path:
            raise Exception("文档parsed_content文件不存在，无法生成模板")
        
        # 更新进度：读取文档（15%）
        self.update_progress(15, "读取文档内容")
        update_task_progress(db, task_id, 15, "读取文档内容", 1, 8)
        
        # 读取parsed_content
        parsed_content_file_abs = os.path.join("/app", document.parsed_content_path)
        if not os.path.exists(parsed_content_file_abs):
            raise Exception(f"parsed_content文件不存在: {parsed_content_file_abs}")
        
        with open(parsed_content_file_abs, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"已读取文档内容: {len(content)} 字符")
        
        # 更新进度：分析文档（30%）
        analysis_step = "智能分段分析" if analysis_mode == "smart_segment" else "全文分块分析"
        self.update_progress(30, f"开始{analysis_step}")
        update_task_progress(db, task_id, 30, f"开始{analysis_step}", 2, 8)
        
        # 根据分析模式生成模板（使用asyncio运行异步函数）
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if analysis_mode == "smart_segment":
                template_config = loop.run_until_complete(
                    TemplateGenerationService.generate_template_smart_segment(
                        content,
                        document.file_name
                    )
                )
            elif analysis_mode == "full_chunk":
                template_config = loop.run_until_complete(
                    TemplateGenerationService.generate_template_full_chunk(
                        content,
                        document.file_name
                    )
                )
            else:
                raise Exception(f"不支持的分析模式: {analysis_mode}")
        finally:
            loop.close()
        
        # 更新进度：验证模板（70%）
        self.update_progress(70, "验证模板配置")
        update_task_progress(db, task_id, 70, "验证模板配置", 3, 8)
        
        # 验证模板配置
        is_valid, errors, warnings = TemplateService.validate_template(
            template_config.get("entity_types", {}),
            template_config.get("edge_types", {}),
            template_config.get("edge_type_map", {})
        )
        
        if not is_valid:
            raise Exception(f"模板验证失败: {', '.join(errors)}")
        
        # 更新进度：保存模板（85%）
        self.update_progress(85, "保存模板到数据库")
        update_task_progress(db, task_id, 85, "保存模板到数据库", 4, 8)
        
        # 生成模板名称（如果未提供）
        if not template_name:
            doc_name = document.file_name.rsplit('.', 1)[0] if '.' in document.file_name else document.file_name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            template_name = f"LLM生成-{doc_name}-{timestamp}"
        
        # 生成模板描述（如果未提供）
        if not description:
            description = f"基于文档'{document.file_name}'自动生成的模板（{analysis_step}）"
        
        # 保存模板到数据库
        template = EntityEdgeTemplate(
            name=template_name,
            description=description,
            category=category,
            entity_types=template_config.get("entity_types", {}),
            edge_types=template_config.get("edge_types", {}),
            edge_type_map=template_config.get("edge_type_map", {}),
            is_default=False,
            is_system=False,
            is_llm_generated=True,
            source_document_id=document_id,
            analysis_mode=analysis_mode,
            llm_provider="local",
            generated_at=datetime.now(),
            usage_count=0
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        logger.info(f"模板生成成功: {template.name} (ID: {template.id})")
        
        # 更新进度：完成（100%）
        self.update_progress(100, "模板生成完成")
        update_task_progress(db, task_id, 100, "模板生成完成", 8, 8)
        
        # 更新任务状态
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.now()
        task.result = {
            "template_id": template.id,
            "template_name": template.name
        }
        db.commit()
        
        return {
            "template_id": template.id,
            "template_name": template.name,
            "entity_types_count": len(template_config.get("entity_types", {})),
            "edge_types_count": len(template_config.get("edge_types", {}))
        }
        
    except Exception as e:
        logger.error(f"生成模板失败: {e}", exc_info=True)
        
        # 更新任务状态为失败
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
        
        raise

