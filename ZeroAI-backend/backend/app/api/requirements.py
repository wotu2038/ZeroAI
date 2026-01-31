from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from app.models.schemas import (
    Requirement, RequirementCreate, RequirementUpdate,
    SimilarRequirementQuery, SimilarRequirementResponse,
    RequirementDocumentGenerateRequest, RequirementDocumentGenerateResponse,
    RequirementDocumentGenerateAsyncRequest,
    LLMChatRequest, LLMResponse
)
from app.services.requirement_service import RequirementService
from app.services.graphiti_service import GraphitiService
from app.services.conversation_service import ConversationService
from app.core.llm_client import llm_client
from app.core.neo4j_client import neo4j_client
from app.core.mysql_client import get_db
from app.core.auth import get_current_user_optional
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.chat_history import ChatHistory, ChatMode
from app.models.user import User
from app.tasks.requirement_generation import generate_requirement_document_task
from sqlalchemy.orm import Session
from fastapi import Depends
from datetime import datetime
import logging
import time
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/requirements", tags=["需求助手"])


@router.post("", response_model=Requirement, status_code=201)
async def create_requirement(
    requirement: RequirementCreate,
    provider: str = Query("qianwen", description="LLM提供商")
):
    """
    创建需求文档
    
    使用方案C（混合方案）：
    1. Graphiti 初步提取
    2. 自定义 Prompt 结构化提取
    3. 合并和增强
    """
    try:
        result = await RequirementService.create_requirement(requirement, provider)
        return result
    except Exception as e:
        logger.error(f"创建需求失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建需求失败: {str(e)}")


@router.get("/{requirement_id}", response_model=Requirement)
async def get_requirement(requirement_id: str):
    """获取需求详情"""
    requirement = RequirementService.get_requirement(requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="需求不存在")
    return requirement


@router.get("", response_model=List[Requirement])
async def list_requirements(
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """获取需求列表"""
    try:
        requirements = RequirementService.list_requirements(limit=limit, offset=offset)
        return requirements
    except Exception as e:
        logger.error(f"获取需求列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取需求列表失败: {str(e)}")


@router.put("/{requirement_id}", response_model=Requirement)
async def update_requirement(
    requirement_id: str,
    requirement: RequirementUpdate
):
    """更新需求"""
    # TODO: 实现更新逻辑
    raise HTTPException(status_code=501, detail="更新功能待实现")


@router.delete("/{requirement_id}", status_code=204)
async def delete_requirement(requirement_id: str):
    """删除需求"""
    # TODO: 实现删除逻辑
    raise HTTPException(status_code=501, detail="删除功能待实现")


@router.post("/similar", response_model=SimilarRequirementResponse)
async def find_similar_requirements(
    query: SimilarRequirementQuery,
    provider: str = Query("qianwen", description="LLM提供商")
):
    """
    查找相似需求（组合方案）
    
    支持两种查询方式：
    1. 基于需求ID：查询与指定需求相似的其他需求
    2. 基于文本：基于查询文本查找相似需求
    
    组合查询包括：
    - 语义相似度（Graphiti）
    - 功能点重合度
    - 模块重合度
    """
    try:
        result = await RequirementService.find_similar_requirements(
            requirement_id=query.requirement_id,
            query_text=query.query_text,
            limit=query.limit,
            include_features=query.include_features,
            include_modules=query.include_modules,
            provider=provider
        )
        return result
    except Exception as e:
        logger.error(f"查找相似需求失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查找相似需求失败: {str(e)}")


@router.post("/generate", response_model=RequirementDocumentGenerateResponse)
async def generate_requirement_document(
    request: RequirementDocumentGenerateRequest,
    provider: str = Query("qianwen", description="LLM提供商")
):
    """
    生成需求文档（同步）
    
    结合新需求 + 相似历史需求，生成新文档
    
    支持格式：
    - markdown（默认）
    - word（待实现）
    - pdf（待实现）
    """
    try:
        result = await RequirementService.generate_requirement_document(
            new_requirement_id=request.new_requirement_id,
            similar_requirement_ids=request.similar_requirement_ids,
            format=request.format,
            provider=provider
        )
        return RequirementDocumentGenerateResponse(**result)
    except Exception as e:
        logger.error(f"生成需求文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成需求文档失败: {str(e)}")


@router.post("/generate-async")
async def generate_requirement_document_async(
    request: RequirementDocumentGenerateAsyncRequest,
    db: Session = Depends(get_db)
):
    """
    异步生成需求文档（使用LangGraph多Agent工作流）
    
    工作流程：
    1. 根据用户问题检索相关内容（Episode、Entity、Edge，必要时Community）
    2. 整合检索结果和相似需求，生成初始文档
    3. 评审文档质量
    4. 根据评审结果优化文档（迭代）
    5. 输出最终文档
    
    支持配置：
    - 最大迭代次数（1-10）
    - 质量阈值（0-100）
    - 检索结果数量限制（5-50）
    - 检索模式（单文档/多文档/全部文档）
    """
    try:
        # 先生成Celery任务ID（避免空字符串导致唯一键冲突）
        celery_task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = TaskQueue(
            task_id=celery_task_id,  # 直接使用生成的ID
            upload_id=0,  # 需求文档生成不需要upload_id
            task_type=TaskType.GENERATE_REQUIREMENT_DOCUMENT.value,
            status=TaskStatus.PENDING.value,
            progress=0,
            current_step="等待处理"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 提交Celery任务
        try:
            celery_task = generate_requirement_document_task.delay(
                task_id=celery_task_id,
                user_query=request.user_query,
                new_requirement_id=request.new_requirement_id,
                similar_requirement_ids=request.similar_requirement_ids,
                format=request.format,
                max_iterations=request.max_iterations,
                quality_threshold=request.quality_threshold,
                retrieval_limit=request.retrieval_limit,
                group_id=request.group_id,
                group_ids=request.group_ids,
                all_documents=request.all_documents,
                use_thinking=request.use_thinking
            )
            
            # 验证Celery任务ID
            if not celery_task or not celery_task.id:
                logger.error(f"Celery任务提交失败：未返回任务ID")
                raise ValueError("Celery任务提交失败：未返回任务ID")
            
            # 如果Celery返回的ID不同，更新任务ID
            if celery_task.id != celery_task_id:
                task.task_id = celery_task.id
                db.commit()
            
            logger.info(f"任务提交成功: celery_task_id={celery_task.id}, db_task_id={celery_task_id}")
            
            return {
                "task_id": celery_task.id,
                "status": "pending",
                "message": "任务已提交"
            }
        except Exception as celery_error:
            logger.error(f"提交Celery任务失败: {celery_error}", exc_info=True)
            # 如果Celery任务提交失败，删除已创建的任务记录
            try:
                db.delete(task)
                db.commit()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"提交Celery任务失败: {str(celery_error)}")
        
    except Exception as e:
        logger.error(f"提交生成任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


# ==================== 智能问答相关端点 ====================

@router.post("/qa/chat", response_model=LLMResponse)
async def qa_chat(
    request: LLMChatRequest,
    group_id: Optional[str] = Query(None, description="文档 group_id（单文档模式）"),
    group_ids: Optional[List[str]] = Query(None, description="文档 group_id 列表（多文档模式）"),
    all_documents: bool = Query(False, description="是否检索全部文档"),
    knowledge_base_id: Optional[int] = Query(None, description="知识库ID（用于保存对话历史）"),
    session_id: Optional[str] = Query(None, description="会话ID（用于Mem0记忆管理）"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    智能问答（增强版）
    
    支持三种模式：
    1. 单文档模式：指定 group_id
    2. 多文档模式：指定 group_ids 列表
    3. 全部文档模式：设置 all_documents=True
    
    增强功能：
    - 文档逐个总结
    - 知识覆盖度分析
    - 知识缺口提示
    - 追问建议
    """
    retrieval_start_time = time.time()
    
    try:
        # 获取最后一条用户消息
        user_messages = [msg for msg in request.messages if msg.get("role") == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="没有用户消息")
        
        last_user_message = user_messages[-1]["content"]
        
        # 确定检索范围
        if all_documents:
            # 全部文档模式：不限制 group_id
            target_group_ids = None
            scope_description = "全部文档"
        elif group_ids:
            # 多文档模式
            target_group_ids = group_ids
            scope_description = f"{len(group_ids)} 个文档"
        elif group_id:
            # 单文档模式
            target_group_ids = [group_id]
            scope_description = f"文档 {group_id}"
        else:
            raise HTTPException(status_code=400, detail="必须指定 group_id、group_ids 或设置 all_documents=True")
        
        # 获取检索方案（从 cross_encoder_mode 映射）
        scheme_map = {
            "default": "default",
            "enhanced": "enhanced",
            "smart": "smart"
        }
        scheme = scheme_map.get(request.cross_encoder_mode if hasattr(request, 'cross_encoder_mode') else "default", "default")
        
        # 使用 ConversationService 进行增强问答
        # 从请求中获取 provider（如果有），默认为 "local"
        provider = getattr(request, 'provider', 'local') if hasattr(request, 'provider') else 'local'
        conversation_service = ConversationService(llm_client=llm_client, provider=provider)
        
        # 准备对话历史（排除最后一条用户消息，因为它是当前问题）
        history = request.messages[:-1] if len(request.messages) > 1 else None
        
        # 获取用户ID和会话ID（用于Mem0记忆管理）
        user_id = str(current_user.id) if current_user else "anonymous"
        # 如果没有提供session_id，生成一个（基于knowledge_base_id）
        if not session_id and knowledge_base_id:
            session_id = f"kb_{knowledge_base_id}"
        elif not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        # 调用增强对话服务
        conversation_response = await conversation_service.chat(
            query=last_user_message,
            group_ids=target_group_ids,
            scheme=scheme,
            history=history,
            top_k=10,
            provider=request.provider,
            user_id=user_id,
            session_id=session_id
        )
        
        # 将 RetrievalResult 转换为字典格式（兼容前端格式）
        retrieval_results = []
        if conversation_response.retrieval_results:
            for result in conversation_response.retrieval_results:
                # 根据 source_type 构建不同的格式
                result_dict = {
                    "type": result.source_type,  # entity, edge, episode, community
                    "id": result.uuid,
                    "score": result.score,
                    "properties": {
                        "name": result.name,
                        "content": result.content,
                        "group_id": result.group_id or ""
                    }
                }
                
                # 根据类型添加特定字段
                if result.source_type == "entity":
                    result_dict["labels"] = ["Entity"]
                elif result.source_type == "edge":
                    result_dict["rel_type"] = result.name
                    # 如果有 metadata，提取 source_name 和 target_name
                    if result.metadata:
                        result_dict["source_name"] = result.metadata.get("source_name", "")
                        result_dict["target_name"] = result.metadata.get("target_name", "")
                elif result.source_type == "community":
                    # Community 可能有 member_count 等信息
                    if result.metadata:
                        result_dict["properties"]["member_count"] = result.metadata.get("member_count", 0)
                        result_dict["properties"]["summary"] = result.metadata.get("summary", "")
                        result_dict["properties"]["member_names"] = result.metadata.get("member_names", [])
                
                retrieval_results.append(result_dict)
        
        # 构建增强的回答内容
        answer_content = conversation_response.answer
        
        # 添加知识覆盖度信息
        if conversation_response.coverage_analysis:
            coverage = conversation_response.coverage_analysis
            coverage_level_cn = {"high": "高", "medium": "中", "low": "低"}.get(coverage.get("coverage_level", "low"), "低")
            answer_content += f"\n\n📊 **知识覆盖度**: {coverage_level_cn} | 基于{coverage.get('document_count', 0)}个文档"
        
        # 添加文档总结部分
        if conversation_response.document_summaries:
            answer_content += "\n\n---\n\n### 📄 相关文档总结\n\n"
            for idx, doc_summary in enumerate(conversation_response.document_summaries[:5], 1):
                kb_prefix = f"【{doc_summary.knowledge_base_name}】" if doc_summary.knowledge_base_name else ""
                answer_content += f"📄 [{idx}] {kb_prefix}{doc_summary.document_name} | 相关度: {doc_summary.relevance_score:.0f}%\n"
                answer_content += f"   • 关系: {doc_summary.relationship}\n"
                if doc_summary.key_content:
                    answer_content += f"   • 重点: {doc_summary.key_content[:100]}\n"
                if doc_summary.suggestion:
                    answer_content += f"   • 建议: {doc_summary.suggestion}\n"
                answer_content += f"   • [查看文档]({doc_summary.preview_url})\n\n"
        
        # 添加知识缺口提示
        if conversation_response.knowledge_gaps:
            answer_content += f"\n⚠️ **知识缺口提示**: 知识库中暂无以下相关信息，建议补充相关文档：\n"
            for gap in conversation_response.knowledge_gaps:
                answer_content += f"   - {gap}\n"
        
        # 添加追问建议
        if conversation_response.follow_up_questions:
            answer_content += "\n\n---\n\n### 💭 您可能还想问\n\n"
            for question in conversation_response.follow_up_questions:
                answer_content += f"• {question}\n"
        
        retrieval_time = (time.time() - retrieval_start_time) * 1000
        
        # 转换文档总结为字典格式
        document_summaries_dict = []
        for doc_summary in conversation_response.document_summaries:
            document_summaries_dict.append({
                "document_id": doc_summary.document_id,
                "document_name": doc_summary.document_name,
                "upload_id": doc_summary.upload_id,
                "knowledge_base_name": doc_summary.knowledge_base_name,
                "relationship": doc_summary.relationship,
                "key_content": doc_summary.key_content,
                "suggestion": doc_summary.suggestion,
                "relevance_score": doc_summary.relevance_score,
                "preview_url": doc_summary.preview_url,
                "has_smart_summary": doc_summary.has_smart_summary
            })
        
        logger.info(f"增强问答完成，基于 {conversation_response.retrieval_count} 个检索结果，{len(conversation_response.document_summaries)} 个文档总结")
        
        # 保存对话历史到数据库（如果用户已登录）
        if current_user:
            try:
                # 获取最后一条用户消息
                user_message = last_user_message
                assistant_message = answer_content
                
                # 构建检索摘要
                retrieval_summary = {
                    "count": conversation_response.retrieval_count,
                    "time_ms": retrieval_time,
                    "scheme": scheme,
                    "document_count": len(document_summaries_dict)
                }
                
                # 确定 group_ids（用于多文档模式）
                final_group_ids = None
                if group_ids:
                    final_group_ids = group_ids
                elif group_id:
                    final_group_ids = [group_id]
                
                # 创建对话历史记录
                chat_history = ChatHistory(
                    user_id=current_user.id,
                    knowledge_base_id=knowledge_base_id,
                    chat_mode=ChatMode.CONVERSATION,
                    group_ids=final_group_ids,
                    all_documents="true" if all_documents else "false",
                    retrieval_scheme=scheme,
                    provider=request.provider if hasattr(request, 'provider') else "local",
                    use_thinking="true" if (hasattr(request, 'use_thinking') and request.use_thinking) else "false",
                    user_message=user_message,
                    assistant_message=assistant_message,
                    retrieval_summary=retrieval_summary,
                    retrieval_results=retrieval_results if retrieval_results else None  # 保存完整的检索结果（如果存在）
                )
                
                db.add(chat_history)
                db.commit()
                logger.info(f"对话历史已保存: user_id={current_user.id}, kb_id={knowledge_base_id}, retrieval_results_count={len(retrieval_results) if retrieval_results else 0}")
            except Exception as e:
                logger.warning(f"保存对话历史失败（不影响主流程）: {e}")
                db.rollback()
        
        return LLMResponse(
            content=answer_content,
            answer=answer_content,  # 兼容前端
            retrieval_results=retrieval_results,
            retrieval_count=conversation_response.retrieval_count,
            retrieval_time=retrieval_time,
            has_context=conversation_response.retrieval_count > 0,
            document_summaries=document_summaries_dict,
            knowledge_coverage=conversation_response.coverage_analysis,
            knowledge_gaps=conversation_response.knowledge_gaps,
            follow_up_questions=conversation_response.follow_up_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"问答失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"问答失败: {str(e)}")


@router.get("/qa/history")
async def get_chat_history(
    knowledge_base_id: Optional[int] = Query(None, description="知识库ID（可选，用于筛选）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取对话历史记录
    
    如果用户未登录，返回空列表
    """
    if not current_user:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    
    try:
        # 构建查询
        query = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id)
        
        # 如果指定了知识库ID，进行筛选
        if knowledge_base_id:
            query = query.filter(ChatHistory.knowledge_base_id == knowledge_base_id)
        
        # 按创建时间倒序排列
        query = query.order_by(ChatHistory.created_at.desc())
        
        # 分页
        total = query.count()
        histories = query.offset((page - 1) * page_size).limit(page_size).all()
        
        # 转换为字典
        result = [h.to_dict() for h in histories]
        
        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


@router.post("/qa/similar")
async def qa_similar_requirements(
    query_text: str = Query(..., description="查询文本"),
    group_id: Optional[str] = Query(None, description="当前文档 group_id（可选，用于排除自己）"),
    limit: int = Query(5, ge=1, le=20, description="返回结果数量"),
    provider: str = Query("qianwen", description="LLM提供商")
):
    """
    相似需求推荐
    
    根据问题描述，智能推荐相似的历史需求文档
    """
    try:
        from app.core.neo4j_client import neo4j_client
        from app.core.graphiti_client import get_graphiti_instance
        
        # 使用 Graphiti 进行语义搜索，直接搜索文档级 Episode
        logger.info(f"开始查找相似需求: query='{query_text}'")
        
        # 查询所有文档级 Episode
        episode_query = """
        MATCH (e:Episodic)
        WHERE e.name CONTAINS '文档概览'
        RETURN DISTINCT e.group_id as group_id, 
               e.document_name as document_name,
               e.version as version, 
               e.created_at as created_at,
               e.content as content,
               e.uuid as episode_uuid
        ORDER BY e.created_at DESC
        """
        all_episodes = neo4j_client.execute_query(episode_query)
        logger.info(f"查询到 {len(all_episodes)} 个文档级Episode")
        
        if not all_episodes:
            logger.warning("没有找到任何文档级Episode")
            return {
                "query": query_text,
                "similar_documents": [],
                "count": 0
            }
        
        # 使用 Graphiti 进行语义搜索，获取相关的Entity和Edge
        graphiti = get_graphiti_instance(provider)
        related_group_ids = set()
        
        try:
            search_results = await graphiti.search(query=query_text, num_results=limit * 3)
            logger.info(f"语义搜索成功，返回 {len(search_results) if search_results else 0} 个结果")
        
            # 从搜索结果中提取相关的group_id
            # Graphiti返回的是EntityEdge，我们需要找到这些Edge关联的Episode的group_id
            for result in search_results:
                # 获取源节点和目标节点的UUID
                source_uuid = getattr(result, 'source_node_uuid', None)
                target_uuid = getattr(result, 'target_node_uuid', None)
                
                # 查询这些节点关联的Episode的group_id
                for node_uuid in [source_uuid, target_uuid]:
                    if node_uuid:
                        node_episode_query = """
                        MATCH (n {uuid: $uuid})<-[:MENTIONS]-(e:Episodic)
                        WHERE e.name CONTAINS '文档概览'
                        RETURN DISTINCT e.group_id as group_id
                        LIMIT 5
                        """
                        node_episodes = neo4j_client.execute_query(node_episode_query, {"uuid": str(node_uuid)})
                        for ep in node_episodes:
                            gid = ep.get("group_id")
                            if gid:
                                related_group_ids.add(gid)
        except Exception as search_error:
            logger.warning(f"Graphiti semantic search failed: {search_error}")
        
        # 计算每个Episode的相似度
        similar_documents = []
        seen_group_ids = set()
        
        for episode in all_episodes:
            doc_group_id = episode.get("group_id")
            if not doc_group_id or doc_group_id in seen_group_ids:
                continue
            
            # 排除自己
            if group_id and doc_group_id == group_id:
                continue
                    
            # 计算相似度
            content = episode.get("content", "") or ""
            document_name = episode.get("document_name", "") or ""
            
            # 方法1: 如果group_id在related_group_ids中，说明语义搜索找到了相关结果
            similarity_score = 0.0
            if doc_group_id in related_group_ids:
                similarity_score = 0.8  # 语义搜索匹配的默认分数
            
            # 方法2: 关键词匹配（作为补充）
            query_lower = query_text.lower()
            content_lower = content.lower()
            name_lower = document_name.lower()
            
            # 计算关键词匹配度
            matched_chars = 0
            for char in query_lower:
                if char in content_lower or char in name_lower:
                    matched_chars += 1
            
            keyword_score = matched_chars / len(query_text) if query_text else 0.0
            similarity_score = max(similarity_score, keyword_score * 0.6)  # 关键词匹配权重较低
            
            # 只保留有相似度的文档
            if similarity_score > 0.1:
                    seen_group_ids.add(doc_group_id)
                    similar_documents.append({
                        "group_id": doc_group_id,
                    "document_name": document_name,
                    "version": episode.get("version", ""),
                    "created_at": episode.get("created_at"),
                    "similarity_score": round(similarity_score, 3)
                })
        
        # 按相似度排序
        similar_documents.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        similar_documents = similar_documents[:limit]
        
        logger.info(f"找到 {len(similar_documents)} 个相似文档")
        
        return {
            "query": query_text,
            "similar_documents": similar_documents,
            "count": len(similar_documents)
        }
    except Exception as e:
        logger.error(f"查找相似需求失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查找相似需求失败: {str(e)}")


@router.post("/qa/analyze")
async def qa_analyze_requirement(
    group_id: str = Query(..., description="文档 group_id"),
    provider: str = Query("qianwen", description="LLM提供商")
):
    """
    需求分析
    
    分析需求文档的完整性、一致性，提供改进建议
    """
    try:
        # 查询该文档的所有 Episode
        episode_query = """
        MATCH (e:Episodic)
        WHERE e.group_id = $group_id
        RETURN e.uuid as uuid, e.name as name, e.content as content,
               e.version as version, e.created_at as created_at
        ORDER BY e.created_at ASC
        """
        episodes = neo4j_client.execute_query(episode_query, {"group_id": group_id})
        
        if not episodes:
            raise HTTPException(status_code=404, detail=f"未找到文档: group_id={group_id}")
        
        # 构建文档内容摘要
        document_summary = []
        for ep in episodes:
            ep_name = ep.get("name", "")
            ep_content = ep.get("content", "")[:500]  # 限制长度
            document_summary.append(f"【{ep_name}】\n{ep_content}\n")
        
        full_content = "\n".join(document_summary)
        
        # 使用 LLM 分析文档
        analysis_prompt = f"""请分析以下需求文档的完整性、一致性和质量，并提供改进建议。

文档内容：
{full_content}

请从以下方面进行分析：
1. **完整性**：文档是否包含了需求文档应有的所有部分（概述、功能需求、非功能需求、用例等）
2. **一致性**：文档内部是否存在矛盾或不一致的地方
3. **清晰度**：需求描述是否清晰、明确、可理解
4. **可追溯性**：需求之间是否有清晰的关联关系
5. **改进建议**：针对发现的问题，提供具体的改进建议

请以结构化的方式输出分析结果。"""
        
        analysis_result = await llm_client.chat(
            provider=provider,
            messages=[
                {"role": "system", "content": "你是一个需求文档分析专家，擅长分析需求文档的质量和改进建议。"},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3
        )
        
        logger.info(f"需求分析完成: group_id={group_id}")
        
        return {
            "group_id": group_id,
            "analysis": analysis_result,
            "episode_count": len(episodes)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"需求分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"需求分析失败: {str(e)}")

