"""
需求文档生成任务（Celery任务）
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from celery import Task
from app.core.celery_app import celery_app
from app.core.mysql_client import SessionLocal
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.services.requirement_generation.workflow import run_document_generation_workflow
from app.services.requirement_generation.state import DocumentGenerationState, GenerationStage
from app.services.requirement_service import RequirementService

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


@celery_app.task(bind=True, base=ProgressTask, name="generate_requirement_document_task")
def generate_requirement_document_task(
    self,
    task_id: str,
    user_query: str,
    new_requirement_id: Optional[str],
    similar_requirement_ids: List[str],
    format: str,
    max_iterations: int,
    quality_threshold: float,
    retrieval_limit: int,
    group_id: Optional[str] = None,
    group_ids: Optional[List[str]] = None,
    all_documents: bool = False,
    use_thinking: bool = False
):
    """
    异步生成需求文档任务
    
    Args:
        self: Celery任务实例
        task_id: 任务ID
        user_query: 用户问题/需求描述
        new_requirement_id: 新需求ID（可选）
        similar_requirement_ids: 相似历史需求ID列表
        format: 文档格式（markdown/word/pdf）
        max_iterations: 最大迭代次数
        quality_threshold: 质量阈值
        retrieval_limit: 检索结果数量限制
        group_id: 单文档模式（可选）
        group_ids: 多文档模式（可选）
        all_documents: 全部文档模式
    """
    db = SessionLocal()
    
    try:
        # 更新任务状态为运行中
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.now()
            db.commit()
        
        # 初始化状态
        state: DocumentGenerationState = {
            "user_query": user_query,
            "new_requirement_id": new_requirement_id,
            "similar_requirement_ids": similar_requirement_ids,
            "format": format,
            "max_iterations": max_iterations,
            "quality_threshold": quality_threshold,
            "retrieval_limit": retrieval_limit,
            "use_thinking": use_thinking,
            "group_id": group_id,
            "group_ids": group_ids,
            "all_documents": all_documents,
            "retrieved_content": [],
            "new_requirement": {},
            "similar_requirements": [],
            "current_document": "",
            "review_report": None,
            "quality_score": 0.0,
            "iteration_count": 0,
            "current_stage": GenerationStage.INIT,
            "should_continue": True,
            "is_final": False,
            "task_id": task_id,
            "progress": 0,
            "current_step": "初始化"
        }
        
        # 加载需求数据
        self.update_progress(5, "加载需求数据")
        update_task_progress(db, task_id, 5, "加载需求数据")
        
        # 加载新需求（如果提供了ID）
        if new_requirement_id:
            new_req = RequirementService.get_requirement(new_requirement_id)
            if new_req:
                state["new_requirement"] = {
                    "id": new_req.id,
                    "name": new_req.name,
                    "description": new_req.description,
                    "content": new_req.content,
                    "version": new_req.version
                }
        
        # 加载相似历史需求
        similar_reqs = []
        for req_id in similar_requirement_ids:
            req = RequirementService.get_requirement(req_id)
            if req:
                similar_reqs.append({
                    "id": req.id,
                    "name": req.name,
                    "description": req.description,
                    "content": req.content,
                    "version": req.version
                })
        state["similar_requirements"] = similar_reqs
        
        # 执行工作流（带进度回调）
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def progress_callback(current_state: DocumentGenerationState):
            """进度回调"""
            progress = current_state.get("progress", 0)
            step = current_state.get("current_step", "")
            self.update_progress(progress, step)
            update_task_progress(db, task_id, progress, step)
        
        # 运行工作流
        final_state = loop.run_until_complete(
            run_document_generation_workflow(state)
        )
        
        # 保存结果
        document_id = str(uuid.uuid4())
        document_name = f"{state.get('new_requirement', {}).get('name', '需求文档')}_生成文档_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        result = {
            "document_id": document_id,
            "document_name": document_name,
            "format": format,
            "content": final_state["current_document"],
            "quality_score": final_state["quality_score"],
            "iteration_count": final_state["iteration_count"],
            "retrieved_content_count": len(final_state["retrieved_content"]),
            "review_report": final_state.get("review_report")
        }
        
        # 更新任务状态
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.current_step = "处理完成"
            task.result = result
            task.completed_at = datetime.now()
            db.commit()
        
        logger.info(f"需求文档生成完成: task_id={task_id}, quality_score={final_state['quality_score']:.1f}")
        
        loop.close()
        return result
        
    except Exception as e:
        logger.error(f"生成需求文档失败: {e}", exc_info=True)
        
        # 更新任务状态为失败
        try:
            task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_message = str(e)
                task.completed_at = datetime.now()
                db.commit()
        except:
            pass
        
        raise
    
    finally:
        db.close()

