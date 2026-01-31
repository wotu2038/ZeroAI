"""
构建Community任务（Celery任务）
"""
import logging
from datetime import datetime
from typing import List, Optional
from celery import Task
from app.core.celery_app import celery_app
from app.core.mysql_client import SessionLocal
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.document_upload import DocumentUpload
from app.core.graphiti_client import get_graphiti_instance
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties
from app.core.llm_client import get_llm_client

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


@celery_app.task(bind=True, base=ProgressTask, name="build_communities_task")
def build_communities_task(
    self,
    task_id: str,
    upload_id: int,
    scope: str,
    group_ids: Optional[List[str]],
    provider: str,
    use_thinking: bool = False
):
    """
    异步构建Community任务（步骤6）
    
    Args:
        self: Celery任务实例
        task_id: 任务ID
        upload_id: 文档上传ID
        scope: 构建范围 'current' 或 'cross'
        group_ids: 跨文档时的group_id列表
        provider: LLM提供商
        use_thinking: 是否启用Thinking模式（仅本地大模型支持）
    """
    db = SessionLocal()
    
    try:
        # 更新任务状态为运行中
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.now()
            db.commit()
        
        # 更新进度：初始化（5%）
        self.update_progress(5, "初始化：验证参数和文档")
        update_task_progress(db, task_id, 5, "初始化：验证参数和文档", 0, 10)
        
        # 查询文档
        document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
        if not document:
            raise Exception(f"文档不存在: upload_id={upload_id}")
        
        # 确定要使用的group_ids
        target_group_ids = []
        
        if scope == "current":
            # 当前文档
            if not document.document_id:
                raise Exception("当前文档尚未完成处理，无法构建Community")
            target_group_ids = [document.document_id]
            logger.info(f"构建当前文档的Community: upload_id={upload_id}, group_id={document.document_id}")
        elif scope == "cross":
            # 跨文档
            if not group_ids or len(group_ids) < 2:
                raise Exception("跨文档构建需要至少选择2个文档")
            target_group_ids = group_ids
            logger.info(f"构建跨文档的Community: upload_id={upload_id}, group_ids={group_ids}")
        else:
            raise Exception(f"无效的构建范围: {scope}")
        
        # 更新进度：开始构建（20%）
        self.update_progress(20, f"开始构建Community（{'当前文档' if scope == 'current' else '跨文档'}）")
        update_task_progress(db, task_id, 20, f"开始构建Community", 1, 10)
        
        # 获取Graphiti实例
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        graphiti = get_graphiti_instance(provider)
        
        # 构建Community
        logger.info(f"开始构建Community，group_ids={target_group_ids}")
        communities_result = loop.run_until_complete(
            graphiti.build_communities(group_ids=target_group_ids)
        )
        logger.info(f"Graphiti build_communities 调用完成")
        
        # 更新进度：查询结果（70%）
        self.update_progress(70, "查询Neo4j中的Community节点")
        update_task_progress(db, task_id, 70, "查询Neo4j中的Community节点", 2, 10)
        
        # 直接从Neo4j查询Community节点
        if len(target_group_ids) == 1:
            communities_query = """
            MATCH (c:Community)
            WHERE c.group_id = $group_id OR 
                  (c.group_id IS NOT NULL AND 
                   (toString(c.group_id) CONTAINS $group_id OR 
                    $group_id IN c.group_id))
            RETURN c.uuid as uuid, c.name as name, c.summary as summary, c.group_id as group_id
            ORDER BY c.name
            """
            communities_data = neo4j_client.execute_query(communities_query, {
                "group_id": target_group_ids[0]
            })
        else:
            communities_query = """
            MATCH (c:Community)
            WHERE any(gid IN $group_ids WHERE 
              c.group_id = gid OR 
              (c.group_id IS NOT NULL AND 
               (toString(c.group_id) CONTAINS gid OR 
                gid IN c.group_id)))
            RETURN c.uuid as uuid, c.name as name, c.summary as summary, c.group_id as group_id
            ORDER BY c.name
            """
            communities_data = neo4j_client.execute_query(communities_query, {
                "group_ids": target_group_ids
            })
        
        logger.info(f"从Neo4j查询到 {len(communities_data)} 个Community节点")
        
        # 更新进度：翻译summary（85%）
        self.update_progress(85, "翻译英文summary为中文")
        update_task_progress(db, task_id, 85, "翻译英文summary为中文", 3, 10)
        
        # 翻译英文summary为中文
        import re
        def is_mostly_english(text):
            if not text:
                return False
            english_chars = len(re.findall(r'[a-zA-Z]', text))
            total_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
            if total_chars == 0:
                return False
            return english_chars / total_chars > 0.5
        
        total_communities = len(communities_data)
        translated_count = 0
        
        for idx, community_data in enumerate(communities_data):
            comm_summary = community_data.get("summary", "")
            comm_name = community_data.get("name", "")
            community_uuid = community_data.get("uuid")
            
            need_translate_name = is_mostly_english(comm_name) and not any('\u4e00' <= c <= '\u9fff' for c in comm_name)
            need_translate_summary = is_mostly_english(comm_summary) and not any('\u4e00' <= c <= '\u9fff' for c in comm_summary)
            
            if need_translate_name or need_translate_summary:
                try:
                    translate_prompt = "请将以下内容翻译成中文，保持原意不变：\n\n"
                    if need_translate_name:
                        translate_prompt += f"名称: {comm_name}\n"
                    if need_translate_summary:
                        translate_prompt += f"摘要: {comm_summary}\n"
                    translate_prompt += "\n请以JSON格式返回，格式：{\"name\": \"翻译后的名称\", \"summary\": \"翻译后的摘要\"}"
                    
                    # 使用LLM翻译（固定使用本地大模型）
                    from openai import AsyncOpenAI
                    from app.core.config import settings
                    
                    local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
                    if not local_base_url.endswith("/v1"):
                        if "/v1" not in local_base_url:
                            local_base_url = f"{local_base_url}/v1"
                    
                    openai_client = AsyncOpenAI(
                        api_key=settings.LOCAL_LLM_API_KEY,
                        base_url=local_base_url,
                        timeout=60.0
                    )
                    
                    # 构建翻译请求参数
                    translate_params = {
                        "model": settings.LOCAL_LLM_MODEL,
                        "messages": [
                            {"role": "user", "content": translate_prompt}
                        ],
                        "temperature": 0.3
                    }
                    
                    # 如果启用Thinking模式，添加extra_body
                    if use_thinking:
                        translate_params["extra_body"] = {"thinking": True}
                    
                    translate_response = loop.run_until_complete(
                        openai_client.chat.completions.create(**translate_params)
                    )
                    translate_result = translate_response.choices[0].message.content
                    
                    # 解析翻译结果
                    import json as json_lib
                    json_match = re.search(r'\{.*\}', translate_result, re.DOTALL)
                    if json_match:
                        translated = json_lib.loads(json_match.group())
                        if need_translate_name and "name" in translated:
                            community_data["name"] = translated["name"]
                        if need_translate_summary and "summary" in translated:
                            community_data["summary"] = translated["summary"]
                        translated_count += 1
                except Exception as e:
                    logger.warning(f"翻译Community {community_uuid} 失败: {e}")
            
            # 更新翻译进度
            if total_communities > 0:
                translate_progress = 85 + int((idx + 1) / total_communities * 10)
                self.update_progress(translate_progress, f"翻译进度 ({idx + 1}/{total_communities})")
                update_task_progress(db, task_id, translate_progress, f"翻译进度 ({idx + 1}/{total_communities})", 3 + idx + 1, 10)
        
        logger.info(f"翻译完成: {translated_count}/{total_communities} 个Community")
        
        # 更新进度：统计实体数量（95%）
        self.update_progress(95, "统计Community包含的实体数量")
        update_task_progress(db, task_id, 95, "统计Community包含的实体数量", 8, 10)
        
        # 构建返回结果
        communities = []
        total_entities = 0
        
        for community_data in communities_data:
            community_uuid = community_data.get("uuid")
            if not community_uuid:
                continue
            
            # 查询该Community包含的实体数量
            entity_count_query = """
            MATCH (c:Community {uuid: $community_uuid})
            OPTIONAL MATCH (c)-[:HAS_MEMBER|CONTAINS]->(e1:Entity)
            OPTIONAL MATCH (e2:Entity)-[:BELONGS_TO]->(c)
            RETURN count(DISTINCT e1) + count(DISTINCT e2) as entity_count
            """
            entity_result = neo4j_client.execute_query(entity_count_query, {
                "community_uuid": community_uuid
            })
            entity_count = entity_result[0].get("entity_count", 0) if entity_result else 0
            total_entities += entity_count
            
            # 处理group_id
            community_group_ids = []
            group_id_value = community_data.get("group_id")
            if group_id_value:
                if isinstance(group_id_value, list):
                    community_group_ids = [str(gid) for gid in group_id_value]
                else:
                    community_group_ids = [str(group_id_value)]
            
            communities.append({
                "uuid": str(community_uuid),
                "name": community_data.get("name") or "未命名Community",
                "summary": community_data.get("summary") or "",
                "entity_count": entity_count,
                "group_ids": community_group_ids
            })
        
        logger.info(f"Community构建完成: 共 {len(communities)} 个Community，包含 {total_entities} 个实体")
        
        # 构建结果
        result = {
            "success": True,
            "communities": communities,
            "statistics": {
                "total_communities": len(communities),
                "total_entities": total_entities,
                "translated_count": translated_count,
                "scope": scope,
                "group_ids": target_group_ids
            }
        }
        
        # 更新任务状态为完成
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.current_step = f"构建完成：共 {len(communities)} 个Community"
            task.completed_steps = 10
            task.result = result
            task.completed_at = datetime.now()
            db.commit()
        
        loop.close()
        return result
        
    except Exception as e:
        logger.error(f"构建Community失败: {e}", exc_info=True)
        
        # 更新任务状态为失败
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
        
        raise
    
    finally:
        db.close()

