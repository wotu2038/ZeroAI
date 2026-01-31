"""
智能对话API

提供文档入库流程和检索生成流程的分步执行API
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.core.mysql_client import SessionLocal, get_db
from sqlalchemy.orm import Session
from app.models.document_upload import DocumentUpload
from app.models.user import User
from app.core.auth import get_current_user_optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligent-chat", tags=["智能对话"])


# ==================== 请求模型 ====================

class Step1GraphitiEpisodeRequest(BaseModel):
    upload_id: int
    provider: Literal["deepseek", "qwen", "kimi"] = Field(default="deepseek", description="LLM提供商（仅支持 deepseek/qwen/kimi）")
    # 模板配置（必选）
    template_mode: str  # "llm_generate" 或 "json_config"（必选，无默认值）
    template_config_json: Optional[Dict[str, Any]] = None  # JSON配置（json_config 模式时必填）


class Step2CogneeBuildRequest(BaseModel):
    upload_id: int
    group_id: Optional[str] = None  # 可选，如果没有则自动生成
    provider: Literal["deepseek", "qwen", "kimi"] = Field(default="deepseek", description="LLM提供商（仅支持 deepseek/qwen/kimi）")
    # 模板配置（cognify阶段）
    cognify_template_mode: str = "llm_generate"  # "llm_generate" 或 "json_config"
    cognify_template_config_json: Optional[Dict[str, Any]] = None  # JSON配置（entity_types, edge_types, edge_type_map）
    # 模板配置（memify阶段）
    memify_template_mode: str = "llm_generate"  # "llm_generate" 或 "json_config"
    memify_template_config_json: Optional[Dict[str, Any]] = None  # JSON配置（extraction和enrichment配置）


class Step3MilvusVectorizeRequest(BaseModel):
    upload_id: int
    group_id: str


class Step4MilvusRecallRequest(BaseModel):
    query: str
    top_k: int = 50
    group_ids: Optional[List[str]] = None


class Step5Neo4jRefineRequest(BaseModel):
    query: str
    recall_results: List[Dict[str, Any]]


class Step6Mem0InjectRequest(BaseModel):
    query: str
    refined_results: List[Dict[str, Any]]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    provider: Literal["deepseek", "qwen", "kimi"] = Field(default="deepseek", description="LLM提供商（仅支持 deepseek/qwen/kimi）")


class Step7LLMGenerateRequest(BaseModel):
    query: str
    retrieval_results: Optional[List[Dict[str, Any]]] = None  # 智能检索结果（可选）
    injected_results: Optional[List[Dict[str, Any]]] = None  # Mem0注入结果（可选）
    provider: Literal["deepseek", "qwen", "kimi"] = Field(default="deepseek", description="LLM提供商（仅支持 deepseek/qwen/kimi）")
    user_id: Optional[str] = None  # 用户ID（用于Mem0记忆保存）
    session_id: Optional[str] = None  # 会话ID（用于Mem0记忆保存）


class Mem0ChatRequest(BaseModel):
    """Mem0 独立问答请求"""
    query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    provider: Literal["deepseek", "qwen", "kimi"] = Field(default="deepseek", description="LLM提供商（仅支持 deepseek/qwen/kimi）")


class SmartRetrievalRequest(BaseModel):
    """智能检索请求"""
    query: str
    top_k: int = 50
    top3: bool = True
    group_ids: Optional[List[str]] = None
    enable_refine: bool = True
    enable_bm25: bool = True
    enable_graph_traverse: bool = True


# ==================== 文档入库流程 API ====================

@router.post("/step1/graphiti-episode")
async def step1_graphiti_episode(
    request: Step1GraphitiEpisodeRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤1: Graphiti文档级处理
    
    创建文档级Episode，提取Entity和Edge
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        # 验证文档存在
        document = db.query(DocumentUpload).filter(DocumentUpload.id == request.upload_id).first()
        if not document:
            raise HTTPException(status_code=404, detail=f"文档不存在: upload_id={request.upload_id}")
        
        # 检查文档是否已解析
        if not document.parsed_content_path:
            raise HTTPException(status_code=400, detail="文档尚未解析，请先完成文档解析")
        
        # 验证 template_mode
        if request.template_mode not in ["llm_generate", "json_config"]:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的 template_mode: {request.template_mode}，只支持 'llm_generate' 或 'json_config'"
            )
        
        # 验证 json_config 模式必须提供 template_config_json
        if request.template_mode == "json_config" and not request.template_config_json:
            raise HTTPException(
                status_code=400,
                detail="json_config 模式必须提供 template_config_json 参数"
            )
        
        service = IntelligentChatService()
        result = await service.step1_graphiti_episode(
            upload_id=request.upload_id,
            provider=request.provider,
            template_mode=request.template_mode,
            template_config_json=request.template_config_json
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"步骤1执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/step2/cognee-build")
async def step2_cognee_build(
    request: Step2CogneeBuildRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤2: Cognee章节级处理
    
    构建章节级知识图谱
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        # 验证文档存在
        document = db.query(DocumentUpload).filter(DocumentUpload.id == request.upload_id).first()
        if not document:
            raise HTTPException(status_code=404, detail=f"文档不存在: upload_id={request.upload_id}")
        
        # 检查文档是否已分块
        if not document.chunks_path:
            raise HTTPException(status_code=400, detail="文档尚未分块，请先完成文档分块")
        
        service = IntelligentChatService()
        result = await service.step2_cognee_build(
            upload_id=request.upload_id,
            group_id=request.group_id,  # 可选，如果没有则自动生成
            provider=request.provider,
            cognify_template_mode=request.cognify_template_mode,
            cognify_template_config_json=request.cognify_template_config_json,
            memify_template_mode=request.memify_template_mode,
            memify_template_config_json=request.memify_template_config_json
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"步骤2执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.get("/step2/cognee-graph")
async def get_cognee_graph(
    group_id: str = Query(..., description="文档组ID"),
    limit: int = Query(500, ge=1, le=2000, description="返回节点数量限制")
):
    """
    获取Cognee图谱数据
    
    查询指定group_id的Cognee节点和关系
    """
    try:
        from app.core.neo4j_client import neo4j_client
        from app.core.utils import serialize_neo4j_properties
        
        # 注意：Cognee 创建的节点没有 group_id、dataset_name 或 dataset_id 属性
        # 所以直接查询所有 Cognee 节点（通过标签识别）
        # 如果 Neo4j 中有多个 group_id 的节点，可能需要通过其他方式区分
        query = """
        // 查询所有 Cognee 节点（Cognee 节点没有 group_id 属性，只能通过标签查询）
        MATCH (n)
        WHERE '__Node__' IN labels(n)
           AND ('Entity' IN labels(n)
           OR 'DocumentChunk' IN labels(n)
           OR 'TextDocument' IN labels(n)
           OR 'EntityType' IN labels(n)
           OR 'TextSummary' IN labels(n)
           OR 'KnowledgeNode' IN labels(n))
        WITH collect(DISTINCT n)[0..$limit] as nodes
        
        // 查询这些节点之间的关系
        MATCH (a)-[r]->(b)
        WHERE a IN nodes AND b IN nodes
        
        WITH nodes, collect(DISTINCT r)[0..$limit] as relations
        
        RETURN 
          [node IN nodes | {
            id: id(node),
            labels: labels(node),
            properties: properties(node)
          }] as nodes,
          [rel IN relations | {
            id: id(rel),
            source: id(startNode(rel)),
            target: id(endNode(rel)),
            type: type(rel),
            properties: properties(rel)
          }] as edges
        """
        
        result = neo4j_client.execute_query(query, {
            "group_id": group_id,
            "limit": limit
        })
        
        if not result:
            return {"nodes": [], "edges": []}
        
        data = result[0]
        
        # 处理节点
        nodes_dict = {}
        for node_data in data.get("nodes", []):
            if node_data.get("id") is not None:
                node_id = str(node_data["id"])
                props = node_data.get("properties", {})
                nodes_dict[node_id] = {
                    "id": node_id,
                    "labels": node_data.get("labels", []),
                    "name": props.get("name", ""),
                    "type": node_data.get("labels", ["Node"])[0] if node_data.get("labels") else "Node",
                    "properties": serialize_neo4j_properties(props)
                }
        
        # 处理边
        edges = []
        for edge_data in data.get("edges", []):
            if edge_data.get("id") is not None and edge_data.get("source") is not None:
                source_id = str(edge_data["source"])
                target_id = str(edge_data["target"])
                # 确保source和target节点都存在
                if source_id in nodes_dict and target_id in nodes_dict:
                    edges.append({
                        "id": str(edge_data["id"]),
                        "source": source_id,
                        "target": target_id,
                        "type": edge_data.get("type", ""),
                        "properties": serialize_neo4j_properties(edge_data.get("properties", {}))
                    })
        
        return {
            "nodes": list(nodes_dict.values()),
            "edges": edges,
            "group_id": group_id
        }
        
    except Exception as e:
        logger.error(f"获取Cognee图谱数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/step3/milvus-vectorize")
async def step3_milvus_vectorize(
    request: Step3MilvusVectorizeRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤3: Milvus向量化处理
    
    生成文档摘要、Requirement、流程/规则向量并存储到Milvus
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        # 验证文档存在
        document = db.query(DocumentUpload).filter(DocumentUpload.id == request.upload_id).first()
        if not document:
            raise HTTPException(status_code=404, detail=f"文档不存在: upload_id={request.upload_id}")
        
        service = IntelligentChatService()
        result = await service.step3_milvus_vectorize(
            upload_id=request.upload_id,
            group_id=request.group_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"步骤3执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


# ==================== 检索生成流程 API ====================

@router.post("/step4/milvus-recall")
async def step4_milvus_recall(
    request: Step4MilvusRecallRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤4: Milvus快速召回
    
    向量相似性检索，返回Top K相似结果
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        service = IntelligentChatService()
        result = await service.step4_milvus_recall(
            query=request.query,
            top_k=request.top_k,
            group_ids=request.group_ids
        )
        
        return result
        
    except Exception as e:
        logger.error(f"步骤4执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/step5/neo4j-refine")
async def step5_neo4j_refine(
    request: Step5Neo4jRefineRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤5: Neo4j精筛
    
    使用Graphiti和Cognee联合查询，精筛Milvus召回结果
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        service = IntelligentChatService()
        result = await service.step5_neo4j_refine(
            query=request.query,
            recall_results=request.recall_results
        )
        
        return result
        
    except Exception as e:
        logger.error(f"步骤5执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/step6/mem0-inject")
async def step6_mem0_inject(
    request: Step6Mem0InjectRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤6: Mem0记忆注入
    
    检索用户偏好、会话上下文、反馈记忆，注入到检索结果
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        # 获取用户ID
        user_id = str(current_user.id) if current_user else request.user_id or "anonymous"
        
        service = IntelligentChatService()
        result = await service.step6_mem0_inject(
            query=request.query,
            refined_results=request.refined_results,
            user_id=user_id,
            session_id=request.session_id,
            provider=request.provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"步骤6执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/mem0-chat")
async def mem0_chat(
    request: Mem0ChatRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Mem0 独立问答接口
    
    用于验证 Mem0 的上下文管理能力：
    - 检索 Mem0 记忆
    - 使用 LLM 生成回答（结合记忆和对话历史）
    - 保存对话到 Mem0
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        # 获取用户ID
        user_id = str(current_user.id) if current_user else request.user_id or "anonymous"
        
        service = IntelligentChatService()
        result = await service.mem0_chat(
            query=request.query,
            user_id=user_id,
            session_id=request.session_id,
            conversation_history=request.conversation_history,
            provider=request.provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Mem0 问答失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/step7/llm-generate")
async def step7_llm_generate(
    request: Step7LLMGenerateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    步骤7: LLM生成
    
    生成新需求文档、对比分析、复用建议、风险提示
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        # 获取用户ID（优先使用 current_user，否则使用 request 中的 user_id）
        user_id = str(current_user.id) if current_user else request.user_id or "anonymous"
        
        service = IntelligentChatService()
        result = await service.step7_llm_generate(
            query=request.query,
            retrieval_results=request.retrieval_results or [],
            injected_results=request.injected_results or [],
            provider=request.provider,
            user_id=user_id,
            session_id=request.session_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"步骤7执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


# ==================== 智能检索 API ====================

@router.post("/smart-retrieval")
async def smart_retrieval(
    request: SmartRetrievalRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    智能检索：两阶段检索策略
    
    阶段1：Milvus快速召回（文档级别）
    - 只使用Document相关的四个向量类型
    - 按文档聚合结果
    - 选择Top3文档
    
    阶段2：精细处理（文档级别）
    - 对Top3文档，使用Graphiti和Cognee知识图谱
    - 使用Milvus和Neo4j进行深度检索
    """
    try:
        from app.services.intelligent_chat_service import IntelligentChatService
        
        service = IntelligentChatService()
        result = await service.smart_retrieval(
            query=request.query,
            top_k=request.top_k,
            top3=request.top3,
            group_ids=request.group_ids,
            enable_refine=request.enable_refine,
            enable_bm25=request.enable_bm25,
            enable_graph_traverse=request.enable_graph_traverse
        )
        
        return result
        
    except Exception as e:
        logger.error(f"智能检索执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

