from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import entities, relationships, graph, llm, import_data, requirements, word_document, composite, document_upload, knowledge_management, task_management, template_management, knowledge_base, auth, user_management, document_library, intelligent_chat
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 确保所有模块的日志级别都是 INFO
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.services.requirement_service").setLevel(logging.INFO)
logging.getLogger("app.core.graphiti_client").setLevel(logging.INFO)

app = FastAPI(title="ZeroAI Knowledge Graph API", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(entities.router, prefix="/api/entities", tags=["entities"])
app.include_router(relationships.router, prefix="/api/relationships", tags=["relationships"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(import_data.router, prefix="/api/import", tags=["import"])
app.include_router(requirements.router)  # 需求助手路由（已在router中定义了prefix）
app.include_router(word_document.router)  # Word文档处理路由（已在router中定义了prefix）
app.include_router(composite.router)  # 组合管理路由（已在router中定义了prefix）
app.include_router(document_upload.router)  # 文档上传路由（已在router中定义了prefix）
app.include_router(knowledge_management.router)  # 知识管理路由（已在router中定义了prefix）
app.include_router(template_management.router)  # 模板管理路由（已在router中定义了prefix）
app.include_router(task_management.router)  # 任务管理路由（已在router中定义了prefix）
app.include_router(knowledge_base.router)  # 知识库管理路由（已在router中定义了prefix）
app.include_router(auth.router)  # 用户认证路由（已在router中定义了prefix）
app.include_router(user_management.router)  # 用户管理路由（已在router中定义了prefix）
app.include_router(document_library.router)  # 文档库路由（已在router中定义了prefix）
app.include_router(intelligent_chat.router)  # 智能对话路由（已在router中定义了prefix）


# 初始化MySQL数据库表
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    try:
        from app.core.mysql_client import init_db
        init_db()
        logging.info("MySQL数据库初始化完成")
        
        # 初始化默认模板
        try:
            from app.utils.init_default_template import init_default_template
            init_default_template()
            logging.info("默认模板初始化完成")
        except Exception as e:
            logging.warning(f"默认模板初始化失败: {e}")
        
        # 初始化默认管理员用户
        try:
            from app.utils.init_default_user import init_default_user
            init_default_user()
            logging.info("默认用户初始化完成")
        except Exception as e:
            logging.warning(f"默认用户初始化失败: {e}")
        
        # 初始化 Milvus Collections（如果启用）
        try:
            from app.core.config import settings
            if settings.ENABLE_MILVUS and settings.MILVUS_HOST:
                from app.services.milvus_service import get_milvus_service
                milvus = get_milvus_service()
                if milvus.is_available():
                    milvus.ensure_collections()
                    logging.info("Milvus Collections 初始化完成")
                else:
                    logging.warning("Milvus 不可用，跳过初始化")
        except Exception as e:
            logging.warning(f"Milvus 初始化失败: {e}")
        
        # 初始化 Neo4j 索引（确保所有必需的索引存在）
        try:
            from app.core.neo4j_client import neo4j_client
            _init_neo4j_indices()
            logging.info("Neo4j 索引初始化完成")
        except Exception as e:
            logging.warning(f"Neo4j 索引初始化失败: {e}")
        
        # 初始化 Cognee Neo4j 配置（必须在导入 Cognee 之前设置）
        # 这是解决 Cognee 无法创建 Neo4j 节点的关键
        try:
            from app.utils.init_cognee_neo4j_config import init_cognee_neo4j_config
            success = init_cognee_neo4j_config()
            if success:
                logging.info("✅ Cognee Neo4j 配置初始化完成（FastAPI 启动时）")
            else:
                logging.warning("⚠️ Cognee Neo4j 配置初始化未完全成功")
        except Exception as e:
            logging.warning(f"Cognee Neo4j 配置初始化失败: {e}")
        
        # 初始化 Cognee LLM 配置（解决 @lru_cache + Pipeline 多进程配置传递问题）
        try:
            from app.utils.init_cognee_llm_config import init_cognee_llm_config
            success = await init_cognee_llm_config()
            if success:
                logging.info("✅ Cognee LLM 配置初始化完成（FastAPI 启动时）")
            else:
                logging.warning("⚠️ Cognee LLM 配置初始化未完全成功，但环境变量已设置")
        except Exception as e:
            logging.warning(f"Cognee LLM 配置初始化失败: {e}")
    except Exception as e:
        logging.warning(f"MySQL数据库初始化失败（可能数据库未配置）: {e}")


def _init_neo4j_indices():
    """初始化 Neo4j 索引（Range 索引和 Fulltext 索引）"""
    from app.core.neo4j_client import neo4j_client
    
    # Range 索引
    range_indices = [
        "CREATE INDEX entity_uuid IF NOT EXISTS FOR (n:Entity) ON (n.uuid)",
        "CREATE INDEX entity_group_id IF NOT EXISTS FOR (n:Entity) ON (n.group_id)",
        "CREATE INDEX name_entity_index IF NOT EXISTS FOR (n:Entity) ON (n.name)",
        "CREATE INDEX created_at_entity_index IF NOT EXISTS FOR (n:Entity) ON (n.created_at)",
        "CREATE INDEX episode_uuid IF NOT EXISTS FOR (n:Episodic) ON (n.uuid)",
        "CREATE INDEX episode_group_id IF NOT EXISTS FOR (n:Episodic) ON (n.group_id)",
        "CREATE INDEX created_at_episodic_index IF NOT EXISTS FOR (n:Episodic) ON (n.created_at)",
        "CREATE INDEX valid_at_episodic_index IF NOT EXISTS FOR (n:Episodic) ON (n.valid_at)",
        "CREATE INDEX community_uuid IF NOT EXISTS FOR (n:Community) ON (n.uuid)",
        "CREATE INDEX community_group_id IF NOT EXISTS FOR (n:Community) ON (n.group_id)",
        "CREATE INDEX relation_uuid IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.uuid)",
        "CREATE INDEX relation_group_id IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.group_id)",
        "CREATE INDEX name_edge_index IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.name)",
        "CREATE INDEX created_at_edge_index IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.created_at)",
        "CREATE INDEX expired_at_edge_index IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.expired_at)",
        "CREATE INDEX valid_at_edge_index IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.valid_at)",
        "CREATE INDEX invalid_at_edge_index IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON (e.invalid_at)",
        "CREATE INDEX mention_uuid IF NOT EXISTS FOR ()-[e:MENTIONS]-() ON (e.uuid)",
        "CREATE INDEX mention_group_id IF NOT EXISTS FOR ()-[e:MENTIONS]-() ON (e.group_id)",
        "CREATE INDEX has_member_uuid IF NOT EXISTS FOR ()-[e:HAS_MEMBER]-() ON (e.uuid)",
    ]
    
    # Fulltext 索引（全文搜索）
    fulltext_indices = [
        "CREATE FULLTEXT INDEX episode_content IF NOT EXISTS FOR (e:Episodic) ON EACH [e.content, e.source, e.source_description, e.group_id]",
        "CREATE FULLTEXT INDEX node_name_and_summary IF NOT EXISTS FOR (n:Entity) ON EACH [n.name, n.summary, n.group_id]",
        "CREATE FULLTEXT INDEX community_name IF NOT EXISTS FOR (n:Community) ON EACH [n.name, n.group_id]",
        "CREATE FULLTEXT INDEX edge_name_and_fact IF NOT EXISTS FOR ()-[e:RELATES_TO]-() ON EACH [e.name, e.fact, e.group_id]",
    ]
    
    # 创建 Range 索引
    for index_query in range_indices:
        try:
            neo4j_client.execute_write(index_query)
            logging.debug(f"Neo4j Range 索引创建/检查完成: {index_query[:50]}...")
        except Exception as e:
            logging.warning(f"Neo4j Range 索引创建失败（可能已存在）: {index_query[:50]}... - {e}")
    
    # 创建 Fulltext 索引
    for index_query in fulltext_indices:
        try:
            neo4j_client.execute_write(index_query)
            logging.debug(f"Neo4j Fulltext 索引创建/检查完成: {index_query[:50]}...")
        except Exception as e:
            logging.warning(f"Neo4j Fulltext 索引创建失败（可能已存在）: {index_query[:50]}... - {e}")


@app.get("/")
async def root():
    return {"message": "ZeroAI Knowledge Graph API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

