"""
Cognee 服务

使用 Cognee 为章节内容构建知识图谱
参考: https://github.com/topoteretes/cognee
"""
import logging
import asyncio
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

# Cognee 客户端（延迟导入）
_cognee = None


def get_cognee():
    """获取 Cognee 实例（单例）"""
    global _cognee
    if _cognee is None:
        try:
            logger.info("get_cognee() 开始执行，_cognee=None")
            # 关键：在导入 Cognee 之前设置环境变量
            # Cognee 在导入时会读取环境变量，所以必须先设置
            import os
            logger.info("开始设置环境变量...")
            if hasattr(settings, 'LOCAL_LLM_API_KEY') and settings.LOCAL_LLM_API_KEY:
                os.environ["LLM_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["OPENAI_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["LLM_PROVIDER"] = "openai"
                
                # 设置 endpoint（先设置 endpoint，再设置 model，因为 model 设置依赖于 endpoint）
                if hasattr(settings, 'LOCAL_LLM_API_BASE_URL') and settings.LOCAL_LLM_API_BASE_URL:
                    local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
                    if not local_base_url.endswith('/v1'):
                        if '/v1' not in local_base_url:
                            local_base_url = f"{local_base_url}/v1"
                    os.environ["OPENAI_BASE_URL"] = local_base_url
                    os.environ["LLM_ENDPOINT"] = local_base_url
                    # 对于 litellm，需要明确指定这是自定义 OpenAI 端点
                    # 使用 "openai/model_name" 格式，litellm 会使用 OPENAI_BASE_URL
                    # 注意：如果模型名称是完整路径（如 "/home/llm_deploy/Qwen3-32B"），需要保留完整路径
                    if hasattr(settings, 'LOCAL_LLM_MODEL') and settings.LOCAL_LLM_MODEL:
                        model_name = settings.LOCAL_LLM_MODEL
                        # 如果模型名称是完整路径，保留完整路径（服务器需要完整路径）
                        # 如果只是模型名，则直接使用
                        if model_name.startswith('/'):
                            # 完整路径，保留原样
                            os.environ["LLM_MODEL"] = f"openai/{model_name}"
                        else:
                            # 只是模型名，直接使用
                            os.environ["LLM_MODEL"] = f"openai/{model_name}"
                    else:
                        os.environ["LLM_MODEL"] = "openai/gpt-4"
                logger.info(f"环境变量设置完成 - LLM_MODEL={os.environ.get('LLM_MODEL')}, OPENAI_BASE_URL={os.environ.get('OPENAI_BASE_URL')}")
            else:
                logger.warning("LOCAL_LLM_API_KEY 未设置")
            
            # 设置 Neo4j 图数据库环境变量（在导入 Cognee 之前）
            # 根据 Cognee 官方文档，这些环境变量必须在导入前设置
            # 注意：使用自托管 Neo4j 时，需要禁用多用户访问控制（ENABLE_BACKEND_ACCESS_CONTROL=false）
            # 因为 neo4j_aura_dev 需要 Neo4j Aura 云服务的认证信息
            os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
            os.environ["GRAPH_DATABASE_PROVIDER"] = "neo4j"
            os.environ["GRAPH_DATABASE_URL"] = settings.NEO4J_URI
            os.environ["GRAPH_DATABASE_NAME"] = "neo4j"
            os.environ["GRAPH_DATABASE_USERNAME"] = settings.NEO4J_USER
            os.environ["GRAPH_DATABASE_PASSWORD"] = settings.NEO4J_PASSWORD
            # 同时设置 NEO4J_* 环境变量（Cognee 可能也需要这些）
            os.environ["NEO4J_URI"] = settings.NEO4J_URI
            os.environ["NEO4J_USERNAME"] = settings.NEO4J_USER
            os.environ["NEO4J_PASSWORD"] = settings.NEO4J_PASSWORD
            # 设置 COGNEE_* 环境变量（Cognee 可能也需要这些）
            os.environ["COGNEE_GRAPH_DB_PROVIDER"] = "neo4j"
            os.environ["COGNEE_GRAPH_DB_NAME"] = "neo4j"
            logger.info(
                f"Neo4j 环境变量已设置: "
                f"GRAPH_DATABASE_PROVIDER={os.environ.get('GRAPH_DATABASE_PROVIDER')}, "
                f"GRAPH_DATABASE_URL={os.environ.get('GRAPH_DATABASE_URL')}, "
                f"NEO4J_USERNAME={os.environ.get('NEO4J_USERNAME')}"
            )
            
            # 设置 Embedding 环境变量（在导入 Cognee 之前）
            # 确保 embedding_endpoint 被正确设置，避免 None 值导致错误
            if hasattr(settings, 'OLLAMA_BASE_URL') and settings.OLLAMA_BASE_URL:
                ollama_base_url = settings.OLLAMA_BASE_URL.rstrip('/')
                if hasattr(settings, 'OLLAMA_EMBEDDING_MODEL') and settings.OLLAMA_EMBEDDING_MODEL:
                    embedding_model = settings.OLLAMA_EMBEDDING_MODEL
                    os.environ["EMBEDDING_PROVIDER"] = "ollama"
                    os.environ["EMBEDDING_MODEL"] = f"ollama/{embedding_model}"
                    os.environ["OLLAMA_BASE_URL"] = ollama_base_url
                    # 关键：设置 embedding_endpoint（OllamaEmbeddingEngine 需要这个）
                    embedding_endpoint = f"{ollama_base_url}/api/embeddings"
                    os.environ["EMBEDDING_ENDPOINT"] = embedding_endpoint
                    os.environ["EMBEDDING_DIMENSIONS"] = "1024"
                    
                    # 设置 tokenizer（Cognee 需要这个来计算 token 数量）
                    # 配置使用 HuggingFace 镜像源或本地缓存
                    # 方案：设置 HF_ENDPOINT 环境变量指向镜像源
                    # 或者使用 transformers 的离线模式
                    tokeniser_model = embedding_model
                    if ':' in tokeniser_model:
                        tokeniser_model = tokeniser_model.split(':')[0]
                    if '/' in tokeniser_model:
                        tokeniser_model = tokeniser_model.split('/')[-1]
                    if 'bge' in tokeniser_model.lower():
                        os.environ["HUGGINGFACE_TOKENIZER"] = f"BAAI/{tokeniser_model}"
                    else:
                        os.environ["HUGGINGFACE_TOKENIZER"] = tokeniser_model
                    
                    # 配置 HuggingFace 镜像源（解决网络不可达问题）
                    # 使用国内镜像源：https://hf-mirror.com
                    # transformers 库会识别这些环境变量
                    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
                    # 同时设置 HF_HUB_BASE_URL（某些版本可能需要）
                    os.environ["HF_HUB_BASE_URL"] = "https://hf-mirror.com"
                    # 设置缓存目录（可选，用于离线使用）
                    # os.environ["HF_HOME"] = "/app/.cache/huggingface"
                    # os.environ["TRANSFORMERS_CACHE"] = "/app/.cache/huggingface/transformers"
                    
                    logger.info(
                        f"Embedding 环境变量已设置: "
                        f"EMBEDDING_PROVIDER={os.environ.get('EMBEDDING_PROVIDER')}, "
                        f"EMBEDDING_ENDPOINT={embedding_endpoint}, "
                        f"EMBEDDING_DIMENSIONS=1024, "
                        f"HUGGINGFACE_TOKENIZER={os.environ.get('HUGGINGFACE_TOKENIZER')}, "
                        f"HF_ENDPOINT={os.environ.get('HF_ENDPOINT')}"
                    )
            
            # ========== 4. 配置向量数据库（Milvus）==========
            # 配置 Cognee 使用 Milvus 而不是默认的 LanceDB
            if hasattr(settings, 'ENABLE_MILVUS') and settings.ENABLE_MILVUS:
                if hasattr(settings, 'MILVUS_HOST') and settings.MILVUS_HOST:
                    # 设置 Milvus 环境变量（必须在导入 Cognee 之前！）
                    milvus_url = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
                    os.environ["VECTOR_DB_PROVIDER"] = "milvus"
                    os.environ["VECTOR_DB_URL"] = milvus_url
                    
                    # 构建认证信息（用户名:密码格式）
                    if hasattr(settings, 'MILVUS_USERNAME') and settings.MILVUS_USERNAME:
                        milvus_key = f"{settings.MILVUS_USERNAME}"
                        if hasattr(settings, 'MILVUS_PASSWORD') and settings.MILVUS_PASSWORD:
                            milvus_key = f"{settings.MILVUS_USERNAME}:{settings.MILVUS_PASSWORD}"
                        os.environ["VECTOR_DB_KEY"] = milvus_key
                    elif hasattr(settings, 'MILVUS_TOKEN') and settings.MILVUS_TOKEN:
                        os.environ["VECTOR_DB_KEY"] = settings.MILVUS_TOKEN
                    
                    logger.info(
                        f"Cognee Milvus 配置: "
                        f"VECTOR_DB_PROVIDER=milvus, "
                        f"VECTOR_DB_URL={milvus_url}, "
                        f"VECTOR_DB_KEY={'已设置' if os.environ.get('VECTOR_DB_KEY') else '未设置'}"
                    )
                else:
                    logger.warning("MILVUS_HOST 未设置，Cognee 将使用默认的 LanceDB")
            else:
                logger.info("ENABLE_MILVUS 未启用，Cognee 将使用默认的 LanceDB")
            
            # 导入并注册 Milvus 适配器（必须在导入 Cognee 之前）
            try:
                from community.adapters.vector.milvus import register  # noqa: F401
                logger.info("✅ Milvus 适配器已注册")
            except ImportError as e:
                logger.warning(f"⚠️ 无法导入 Milvus 适配器: {e}，Cognee 将使用默认向量数据库")
            
            # 现在导入 Cognee（此时所有环境变量已设置）
            logger.info("开始导入 cognee 模块...")
            import cognee
            logger.info("cognee 模块导入成功")
            
            # 可选：使用 config API 作为备用配置（确保 Cognee 使用 Milvus）
            if hasattr(settings, 'ENABLE_MILVUS') and settings.ENABLE_MILVUS:
                if hasattr(settings, 'MILVUS_HOST') and settings.MILVUS_HOST:
                    try:
                        milvus_url = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
                        milvus_key = ""
                        if hasattr(settings, 'MILVUS_USERNAME') and settings.MILVUS_USERNAME:
                            milvus_key = f"{settings.MILVUS_USERNAME}"
                            if hasattr(settings, 'MILVUS_PASSWORD') and settings.MILVUS_PASSWORD:
                                milvus_key = f"{settings.MILVUS_USERNAME}:{settings.MILVUS_PASSWORD}"
                        elif hasattr(settings, 'MILVUS_TOKEN') and settings.MILVUS_TOKEN:
                            milvus_key = settings.MILVUS_TOKEN
                        
                        cognee.config.set_vector_db_config({
                            "vector_db_provider": "milvus",
                            "vector_db_url": milvus_url,
                            "vector_db_key": milvus_key
                        })
                        logger.info("✅ 已通过 config API 设置 Cognee Milvus 配置")
                    except Exception as e:
                        logger.warning(f"⚠️ 通过 config API 设置 Milvus 配置失败: {e}")
            
            # ========== 应用 Monkey Patch 修复 Ollama 响应格式问题 ==========
            # Ollama API 返回格式: {'embedding': [...]}
            # Cognee 期望格式: {'embeddings': [...]} 或 {'data': [{'embedding': [...]}]}
            # 需要修复 OllamaEmbeddingEngine._get_embedding 方法
            try:
                from cognee.infrastructure.databases.vector.embeddings.OllamaEmbeddingEngine import OllamaEmbeddingEngine
                import types
                
                # 创建修复后的方法
                async def fixed_get_embedding(self, prompt: str):
                    """修复后的 _get_embedding 方法，支持 Ollama 标准响应格式"""
                    import aiohttp
                    import os
                    from cognee.shared.utils import create_secure_ssl_context
                    from cognee.shared.rate_limiting import embedding_rate_limiter_context_manager
                    
                    # 修复：从模型名称中移除 "ollama/" 前缀（Ollama API 不接受这个前缀）
                    model_name = self.model
                    if model_name.startswith("ollama/"):
                        model_name = model_name[7:]  # 移除 "ollama/" 前缀
                    
                    payload = {"model": model_name, "prompt": prompt, "input": prompt}
                    
                    headers = {}
                    api_key = os.getenv("LLM_API_KEY")
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    
                    ssl_context = create_secure_ssl_context()
                    connector = aiohttp.TCPConnector(ssl=ssl_context)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with embedding_rate_limiter_context_manager():
                            async with session.post(
                                self.endpoint, json=payload, headers=headers, timeout=60.0
                            ) as response:
                                data = await response.json()
                                
                                # 检查是否有错误
                                if "error" in data:
                                    raise ValueError(f"Ollama API error: {data['error']}")
                                
                                # 修复：支持 Ollama 的标准响应格式 {'embedding': [...]}
                                if "embedding" in data:
                                    return data["embedding"]
                                elif "embeddings" in data:
                                    return data["embeddings"][0]
                                elif "data" in data:
                                    return data["data"][0]["embedding"]
                                else:
                                    raise ValueError(f"Unexpected response format: {list(data.keys())}")
                
                # 应用 monkey patch
                OllamaEmbeddingEngine._get_embedding = fixed_get_embedding
                logger.info("✅ 已应用 OllamaEmbeddingEngine monkey patch（支持 Ollama 标准响应格式）")
            except Exception as e:
                logger.warning(f"⚠️  应用 OllamaEmbeddingEngine monkey patch 失败: {e}，将继续使用原始方法")
            
            _cognee = cognee
            logger.info("Cognee 客户端初始化成功")
        except ImportError as e:
            logger.error(f"Cognee 未安装，请运行: pip install cognee, 错误: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"get_cognee() 执行失败: {e}", exc_info=True)
            raise
    else:
        logger.info("get_cognee() 返回已存在的实例")
    return _cognee


class CogneeService:
    """
    Cognee 服务
    
    使用 Cognee 为章节内容构建知识图谱
    """
    
    def __init__(self):
        logger.info("CogneeService.__init__() 开始执行")
        try:
            logger.info("正在调用 get_cognee()...")
            self.cognee = get_cognee()
            logger.info(f"get_cognee() 成功，cognee 类型: {type(self.cognee)}")
            self._initialized = False
            logger.info("CogneeService.__init__() 完成")
        except Exception as e:
            logger.error(f"CogneeService.__init__() 失败: {e}", exc_info=True)
            raise
    
    async def initialize(self):
        """初始化 Cognee（配置 Neo4j，使用默认的 LanceDB 作为向量数据库）"""
        if self._initialized:
            return
        
        try:
            import os
            
            # ========== 1. 配置 LLM ==========
            # Cognee 需要的环境变量：
            # - LLM_API_KEY: LLM API key
            # - LLM_PROVIDER: LLM provider (如 "openai")
            # - LLM_MODEL: LLM model (格式: "openai/model_name")
            # - LLM_ENDPOINT: LLM endpoint (可选，如果使用自定义 endpoint)
            # - OPENAI_API_KEY: 如果使用 OpenAI provider，也需要这个
            # - OPENAI_BASE_URL: 如果使用自定义 endpoint，需要这个
            if hasattr(settings, 'LOCAL_LLM_API_KEY') and settings.LOCAL_LLM_API_KEY:
                # 强制设置，覆盖已存在的值（确保使用最新配置）
                os.environ["LLM_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["OPENAI_API_KEY"] = settings.LOCAL_LLM_API_KEY
                
                # 设置 LLM provider（必须）
                os.environ["LLM_PROVIDER"] = "openai"
                
                # 注意：LLM_MODEL 会在 endpoint 设置时一起设置，这里不需要单独设置
                
                # 设置 LLM endpoint（如果使用自定义 endpoint）
                if hasattr(settings, 'LOCAL_LLM_API_BASE_URL') and settings.LOCAL_LLM_API_BASE_URL:
                    local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
                    # 确保 URL 包含 /v1
                    if not local_base_url.endswith('/v1'):
                        if '/v1' not in local_base_url:
                            local_base_url = f"{local_base_url}/v1"
                    os.environ["OPENAI_BASE_URL"] = local_base_url
                    # Cognee 也可能需要 LLM_ENDPOINT
                    os.environ["LLM_ENDPOINT"] = local_base_url
            
            # ========== 2. 配置 Neo4j 图数据库 ==========
            # 根据 Cognee 官方文档配置 Neo4j
            # 参考: https://docs.cognee.ai/setup-configuration/graph-databases/neo4j
            
            # 注意：使用自托管 Neo4j 时，需要禁用多用户访问控制（ENABLE_BACKEND_ACCESS_CONTROL=false）
            # 因为 neo4j_aura_dev 需要 Neo4j Aura 云服务的认证信息
            if not os.environ.get("ENABLE_BACKEND_ACCESS_CONTROL"):
                os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
            
            # 图数据库提供商
            if not os.environ.get("GRAPH_DATABASE_PROVIDER"):
                os.environ["GRAPH_DATABASE_PROVIDER"] = "neo4j"
            
            # 图数据库 URL（格式：bolt://host:port）
            if not os.environ.get("GRAPH_DATABASE_URL"):
                neo4j_uri = settings.NEO4J_URI
                os.environ["GRAPH_DATABASE_URL"] = neo4j_uri
            
            # 图数据库名称（Neo4j 默认数据库名）
            if not os.environ.get("GRAPH_DATABASE_NAME"):
                os.environ["GRAPH_DATABASE_NAME"] = "neo4j"
            
            # 图数据库用户名
            if not os.environ.get("GRAPH_DATABASE_USERNAME"):
                os.environ["GRAPH_DATABASE_USERNAME"] = settings.NEO4J_USER
            
            # 图数据库密码
            if not os.environ.get("GRAPH_DATABASE_PASSWORD"):
                os.environ["GRAPH_DATABASE_PASSWORD"] = settings.NEO4J_PASSWORD
            
            logger.info(
                f"Neo4j 配置: "
                f"URL={os.environ.get('GRAPH_DATABASE_URL')}, "
                f"USERNAME={os.environ.get('GRAPH_DATABASE_USERNAME')}, "
                f"NAME={os.environ.get('GRAPH_DATABASE_NAME')}"
            )
            
            # ========== 3. 配置 Embedding 模型 ==========
            # Cognee 默认使用 openai/text-embedding-3-large，但我们的自定义端点没有这个模型
            # 配置使用 Ollama 的 embedding 模型
            if hasattr(settings, 'OLLAMA_BASE_URL') and settings.OLLAMA_BASE_URL:
                # 设置 Ollama embedding 配置
                # Cognee 使用 litellm，可以通过环境变量配置 embedding
                ollama_base_url = settings.OLLAMA_BASE_URL.rstrip('/')
                if hasattr(settings, 'OLLAMA_EMBEDDING_MODEL') and settings.OLLAMA_EMBEDDING_MODEL:
                    # 对于 Ollama，litellm 使用 "ollama/model_name" 格式
                    # 保留完整的模型名称（如 "quentinz/bge-large-zh-v1.5:latest"）
                    embedding_model = settings.OLLAMA_EMBEDDING_MODEL
                    
                    # 设置 embedding provider
                    os.environ["EMBEDDING_PROVIDER"] = "ollama"
                    
                    # 设置 embedding model（格式：ollama/model_name）
                    os.environ["EMBEDDING_MODEL"] = f"ollama/{embedding_model}"
                    
                    # 设置 Ollama base URL
                    os.environ["OLLAMA_BASE_URL"] = ollama_base_url
                    
                    # 设置 embedding endpoint（OllamaEmbeddingEngine 需要完整的 endpoint URL）
                    # 格式：http://host:port/api/embeddings
                    embedding_endpoint = f"{ollama_base_url}/api/embeddings"
                    os.environ["EMBEDDING_ENDPOINT"] = embedding_endpoint
                    
                    # 设置 embedding dimensions（bge-large-zh-v1.5 的维度是 1024）
                    # 这是必需的，否则 Cognee 无法正确初始化向量存储
                    os.environ["EMBEDDING_DIMENSIONS"] = "1024"
                    
                    # 注意：不设置 HUGGINGFACE_TOKENIZER，避免 Cognee 尝试访问 HuggingFace
                    # 我们使用 Ollama 的 embedding 模型，不需要从 HuggingFace 获取 tokenizer
                    # Cognee 应该能够使用默认的 tokenizer 或从 Ollama 获取 token 信息
                    # 如果必须设置，可以考虑使用本地 tokenizer 或禁用此功能
                    # 暂时注释掉，避免网络访问问题
                    # tokeniser_model = embedding_model
                    # if ':' in tokeniser_model:
                    #     tokeniser_model = tokeniser_model.split(':')[0]
                    # if '/' in tokeniser_model:
                    #     tokeniser_model = tokeniser_model.split('/')[-1]
                    # if 'bge' in tokeniser_model.lower():
                    #     os.environ["HUGGINGFACE_TOKENIZER"] = f"BAAI/{tokeniser_model}"
                    # else:
                    #     os.environ["HUGGINGFACE_TOKENIZER"] = tokeniser_model
                    
                    logger.info(
                        f"Cognee Embedding 配置: "
                        f"provider=ollama, model=ollama/{embedding_model}, "
                        f"endpoint={embedding_endpoint}, "
                        f"dimensions=1024, tokeniser={os.environ.get('HUGGINGFACE_TOKENIZER')}"
                    )
            
            # 向量数据库配置已在上面完成（在导入 Cognee 之前）
            # 如果配置了 Milvus，Cognee 将使用 Milvus；否则使用默认的 LanceDB
            
            self._initialized = True
            vector_db_info = "Milvus" if (hasattr(settings, 'ENABLE_MILVUS') and settings.ENABLE_MILVUS and hasattr(settings, 'MILVUS_HOST') and settings.MILVUS_HOST) else "LanceDB (默认)"
            logger.info(
                f"Cognee 初始化完成 - "
                f"图数据库: Neo4j ({settings.NEO4J_URI}), "
                f"向量数据库: {vector_db_info}"
            )
        except Exception as e:
            logger.error(f"Cognee 初始化失败: {e}")
            raise
    
    async def _generate_section_template(
        self,
        section_content: str,
        section_title: str,
        provider: str = "local"
    ) -> Dict[str, Any]:
        """
        为单个章节生成模板
        
        Args:
            section_content: 章节内容
            section_title: 章节标题
            
        Returns:
            模板配置（entity_types, edge_types, edge_type_map）
        """
        from app.services.template_generation_service import TemplateGenerationService
        from app.core.llm_client import get_llm_client
        import json
        import re
        
        logger.info(f"为章节 '{section_title}' 生成模板")
        
        # 使用简化的模板生成 prompt（针对单个章节）
        prompt = f"""你是一个知识图谱模板生成专家。请分析以下章节内容，生成适合的实体和关系模板配置。

章节标题：{section_title}

章节内容：
{section_content[:10000]}

请根据章节内容，识别并生成：

1. **实体类型（entity_types）**：
   - 识别章节中的核心实体
   - 为每个实体类型定义：
     * **description**（必需）：实体类型的描述，说明这个实体类型代表什么（例如："角色实体，代表系统中的各种角色和岗位"）
     * **fields**：字段定义（字段类型、是否必需、描述）
   - ⚠️ **重要：以下字段是系统保留字段，不能使用**：
     - uuid, name, group_id, labels, created_at, name_embedding, summary, attributes
   - 请使用其他字段名，例如：entity_name, title, description, status 等

2. **关系类型（edge_types）**：
   - 识别实体之间的关系类型
   - 为每个关系类型定义：
     * **description**（必需）：关系类型的描述，说明这个关系类型代表什么（例如："审批关系，表示一个实体对另一个实体的审批行为"）
     * **fields**：字段定义
   - ⚠️ **重要：以下字段是系统保留字段，不能使用**：
     - uuid, source_node_uuid, target_node_uuid, name, fact, attributes

3. **关系映射（edge_type_map）**：
   - 定义哪些实体之间可以使用哪些关系
   - 格式：{{"SourceEntity -> TargetEntity": ["EdgeName1", "EdgeName2"]}}

返回标准JSON格式：
{{
  "entity_types": {{
    "EntityName": {{
      "description": "实体类型的描述",
      "fields": {{
        "field_name": {{
          "type": "str|Optional[str]|int|Optional[int]|bool|Optional[bool]",
          "required": true|false,
          "description": "字段描述"
        }}
      }}
    }}
  }},
  "edge_types": {{
    "EdgeName": {{
      "description": "关系类型的描述",
      "fields": {{
        "field_name": {{
          "type": "str|Optional[str]|int|Optional[int]|bool|Optional[bool]",
          "required": true|false,
          "description": "字段描述"
        }}
      }}
    }}
  }},
  "edge_type_map": {{
    "SourceEntity -> TargetEntity": ["EdgeName1", "EdgeName2"]
  }}
}}

只返回JSON，不要其他内容。"""
        
        llm_client = get_llm_client()
        response = await llm_client.chat(
            provider,
            [
                {
                    "role": "system",
                    "content": "你是一个专业的知识图谱模板生成专家，擅长从章节内容中提取实体和关系结构，生成规范的模板配置。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            use_thinking=False
        )
        
        # 解析JSON响应
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                template_config = json.loads(json_match.group())
            else:
                template_config = json.loads(response)
            
            # 后处理：移除保留字段
            template_config = TemplateGenerationService._remove_reserved_fields(template_config)
            
            logger.info(f"章节 '{section_title}' 模板生成成功：{len(template_config.get('entity_types', {}))} 个实体类型，{len(template_config.get('edge_types', {}))} 个关系类型")
            return template_config
        except json.JSONDecodeError as e:
            logger.error(f"解析LLM响应失败: {e}\n响应内容: {response[:500]}")
            # 返回空模板，让 Cognee 使用默认行为
            return {"entity_types": {}, "edge_types": {}, "edge_type_map": {}}
    
    def _template_to_custom_prompt(
        self,
        template_config: Dict[str, Any]
    ) -> str:
        """
        将模板配置转换为 Cognee 的 custom_prompt
        
        Args:
            template_config: 模板配置（entity_types, edge_types, edge_type_map）
            
        Returns:
            custom_prompt 字符串
        """
        entity_types = template_config.get("entity_types", {})
        edge_types = template_config.get("edge_types", {})
        edge_type_map = template_config.get("edge_type_map", {})
        
        # 构建实体类型描述
        entity_types_desc = []
        for entity_name, entity_def in entity_types.items():
            fields_desc = []
            entity_description = ""
            
            if isinstance(entity_def, dict):
                # 获取顶层 description
                entity_description = entity_def.get("description", "")
                
                # 获取字段描述
                if "fields" in entity_def:
                    for field_name, field_def in entity_def["fields"].items():
                        field_type = field_def.get("type", "str")
                        required = field_def.get("required", False)
                        description = field_def.get("description", "")
                        fields_desc.append(f"    - {field_name} ({field_type}, {'必需' if required else '可选'}): {description}")
            
            # 构建实体描述
            entity_desc = f"  - {entity_name}"
            if entity_description:
                entity_desc += f"：{entity_description}"
            if fields_desc:
                entity_desc += "\n" + "\n".join(fields_desc)
            entity_types_desc.append(entity_desc)
        
        # 构建关系类型描述
        edge_types_desc = []
        for edge_name, edge_def in edge_types.items():
            fields_desc = []
            edge_description = ""
            
            if isinstance(edge_def, dict):
                # 获取顶层 description
                edge_description = edge_def.get("description", "")
                
                # 获取字段描述
                if "fields" in edge_def:
                    for field_name, field_def in edge_def["fields"].items():
                        field_type = field_def.get("type", "str")
                        required = field_def.get("required", False)
                        description = field_def.get("description", "")
                        fields_desc.append(f"    - {field_name} ({field_type}, {'必需' if required else '可选'}): {description}")
            
            # 构建关系描述
            edge_desc = f"  - {edge_name}"
            if edge_description:
                edge_desc += f"：{edge_description}"
            if fields_desc:
                edge_desc += "\n" + "\n".join(fields_desc)
            edge_types_desc.append(edge_desc)
        
        # 构建关系映射描述
        edge_map_desc = []
        for key, values in edge_type_map.items():
            if isinstance(values, list):
                edge_map_desc.append(f"  - {key}: {', '.join(values)}")
            else:
                edge_map_desc.append(f"  - {key}: {values}")
        
        # 构建完整的 custom_prompt
        custom_prompt = f"""请根据以下实体和关系类型定义，从文本中提取知识图谱：

**实体类型定义**：
{chr(10).join(entity_types_desc) if entity_types_desc else "  （无预定义实体类型，请根据内容自由识别）"}

**关系类型定义**：
{chr(10).join(edge_types_desc) if edge_types_desc else "  （无预定义关系类型，请根据内容自由识别）"}

**关系映射规则**：
{chr(10).join(edge_map_desc) if edge_map_desc else "  （无预定义关系映射，请根据内容自由识别）"}

**提取要求**：
1. 严格按照上述实体类型和关系类型定义进行提取
2. 实体必须符合定义的实体类型
3. 关系必须符合定义的关系类型和关系映射规则
4. 如果文本中没有符合定义的实体或关系，不要强制提取
5. 确保提取的实体和关系准确反映文本内容

请开始提取知识图谱。"""
        
        return custom_prompt
    
    async def _save_cognee_template_to_db(
        self,
        template_config: Dict[str, Any],
        upload_id: int,
        document_name: str,
        section_count: int,
        template_type: str,
        provider: str = "local"
    ) -> Optional[int]:
        """
        保存 Cognee 生成的章节级别模板到数据库
        
        Args:
            template_config: 模板配置（entity_types, edge_types, edge_type_map）
            upload_id: 文档上传ID
            document_name: 文档名称
            section_count: 章节数量
            template_type: 模板类型（方案1-统一模板 或 方案2-章节级别）
            provider: LLM 提供商
            
        Returns:
            模板ID（如果保存成功），否则返回 None
        """
        try:
            from app.core.mysql_client import SessionLocal
            from app.models.template import EntityEdgeTemplate
            from app.services.template_service import TemplateService
            
            # 验证模板配置
            logger.info(f"开始验证 Cognee 模板: upload_id={upload_id}, document_name={document_name}")
            is_valid, errors, warnings = TemplateService.validate_template(
                template_config.get("entity_types", {}),
                template_config.get("edge_types", {}),
                template_config.get("edge_type_map", {})
            )
            
            if not is_valid:
                logger.warning(f"Cognee 模板验证失败，不保存到数据库: {', '.join(errors)}")
                return None
            
            logger.info(f"Cognee 模板验证通过: 实体类型数={len(template_config.get('entity_types', {}))}, 关系类型数={len(template_config.get('edge_types', {}))}")
            
            # 生成模板名称
            doc_name = document_name.rsplit('.', 1)[0] if '.' in document_name else document_name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            template_name = f"Cognee-章节级别-{doc_name}-{timestamp}"
            
            # 生成模板描述
            description = f"基于文档'{document_name}'的章节内容自动生成的Cognee模板（{template_type}，共{section_count}个章节）"
            
            # 创建模板记录
            db = SessionLocal()
            try:
                template = EntityEdgeTemplate(
                    name=template_name,
                    description=description,
                    category="custom",
                    entity_types=template_config.get("entity_types", {}),
                    edge_types=template_config.get("edge_types", {}),
                    edge_type_map=template_config.get("edge_type_map", {}),
                    is_default=False,
                    is_system=False,
                    is_llm_generated=True,
                    source_document_id=upload_id,
                    analysis_mode=f"cognee_section_{template_type.lower().replace('-', '_')}",
                    llm_provider=provider,
                    generated_at=datetime.now(),
                    usage_count=0
                )
                
                db.add(template)
                db.commit()
                db.refresh(template)
                
                logger.info(
                    f"Cognee 章节级别模板已保存到数据库: "
                    f"template_id={template.id}, "
                    f"name={template_name}, "
                    f"实体类型数={len(template_config.get('entity_types', {}))}, "
                    f"关系类型数={len(template_config.get('edge_types', {}))}"
                )
                
                return template.id
            except Exception as e:
                db.rollback()
                logger.error(f"保存 Cognee 模板到数据库失败: {e}", exc_info=True)
                return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"保存 Cognee 模板到数据库时发生异常: {e}", exc_info=True)
            return None
    
    async def _save_memify_template_to_db(
        self,
        memify_config: Dict[str, Any],
        upload_id: int,
        document_name: str,
        dataset_name: str,
        memify_template_mode: str,
        provider: str = "local"
    ) -> Optional[int]:
        """
        保存 Memify 阶段的配置到数据库
        
        Args:
            memify_config: Memify配置（extraction和enrichment配置）
            upload_id: 文档上传ID
            document_name: 文档名称
            dataset_name: Cognee dataset名称
            memify_template_mode: 模板模式（llm_generate 或 json_config）
            provider: LLM 提供商
            
        Returns:
            模板ID（如果保存成功），否则返回 None
        """
        try:
            from app.core.mysql_client import SessionLocal
            from app.models.template import EntityEdgeTemplate
            
            # 生成模板名称
            doc_name = document_name.rsplit('.', 1)[0] if '.' in document_name else document_name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            mode_label = "LLM自动生成" if memify_template_mode == "llm_generate" else "JSON手动配置"
            template_name = f"Memify-{mode_label}-{doc_name}-{timestamp}"
            
            # 生成模板描述
            description = f"基于文档'{document_name}'的Memify阶段配置（{mode_label}，dataset: {dataset_name}）"
            
            # 将Memify配置转换为模板格式（复用EntityEdgeTemplate表结构）
            # entity_types存储extraction配置，edge_types存储enrichment配置，edge_type_map存储其他元数据
            entity_types = {"extraction": memify_config.get("extraction", {})} if memify_config.get("extraction") else {}
            edge_types = {"enrichment": memify_config.get("enrichment", {})} if memify_config.get("enrichment") else {}
            edge_type_map = {
                "memify_config": memify_config,
                "dataset_name": dataset_name,
                "template_mode": memify_template_mode
            }
            
            # 创建模板记录
            db = SessionLocal()
            try:
                template = EntityEdgeTemplate(
                    name=template_name,
                    description=description,
                    category="custom",
                    entity_types=entity_types,  # 存储extraction配置
                    edge_types=edge_types,  # 存储enrichment配置
                    edge_type_map=edge_type_map,  # 存储完整配置和元数据
                    is_default=False,
                    is_system=False,
                    is_llm_generated=(memify_template_mode == "llm_generate"),
                    source_document_id=upload_id,
                    analysis_mode="cognee_memify",  # 使用analysis_mode区分Memify模板
                    llm_provider=provider,
                    generated_at=datetime.now(),
                    usage_count=0
                )
                
                db.add(template)
                db.commit()
                db.refresh(template)
                
                logger.info(
                    f"Memify 模板已保存到数据库: "
                    f"template_id={template.id}, "
                    f"name={template_name}, "
                    f"mode={memify_template_mode}"
                )
                
                return template.id
            except Exception as e:
                db.rollback()
                logger.error(f"保存 Memify 模板到数据库失败: {e}", exc_info=True)
                return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"保存 Memify 模板到数据库时发生异常: {e}", exc_info=True)
            return None
    
    async def build_section_knowledge_graph(
        self,
        sections: List[Dict[str, Any]],
        group_id: str,
        max_concurrent: int = 3,
        provider: str = "deepseek",
        upload_id: Optional[int] = None,
        document_name: Optional[str] = None,
        # 模板配置（cognify阶段）
        cognify_template_mode: str = "llm_generate",  # "llm_generate" 或 "json_config"
        cognify_template_config_json: Optional[Dict[str, Any]] = None,  # JSON配置
        # 模板配置（memify阶段）
        memify_template_mode: str = "llm_generate",  # "llm_generate" 或 "json_config"
        memify_template_config_json: Optional[Dict[str, Any]] = None  # JSON配置
    ) -> Dict[str, Any]:
        """
        为所有章节构建知识图谱
        
        Args:
            sections: 章节列表，每个包含 title, content, uuid 等
            group_id: 文档组 ID
            max_concurrent: 最大并发数
            provider: LLM 提供商
            upload_id: 文档上传ID（用于保存模板到数据库）
            document_name: 文档名称（用于保存模板到数据库）
            
        Returns:
            构建结果统计
        """
        if not sections:
            logger.warning("章节列表为空，跳过知识图谱构建")
            return {"success": False, "reason": "no_sections"}
        
        await self.initialize()
        
        # 再次确保环境变量已设置（在调用 Cognee API 之前）
        # Cognee 可能在内部重新读取配置，所以需要再次设置
        import os
        
        # 根据 provider 选择配置
        if provider == "deepseek":
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API key not configured")
            os.environ["LLM_API_KEY"] = settings.DEEPSEEK_API_KEY
            os.environ["OPENAI_API_KEY"] = settings.DEEPSEEK_API_KEY
            # Cognee/litellm 可能也需要这些环境变量
            os.environ["LITELLM_API_KEY"] = settings.DEEPSEEK_API_KEY
            os.environ["LLM_PROVIDER"] = "openai"
            # litellm 需要格式：openai/model_name
            deepseek_model = f"openai/{settings.DEEPSEEK_MODEL}" if not settings.DEEPSEEK_MODEL.startswith("openai/") else settings.DEEPSEEK_MODEL
            os.environ["LLM_MODEL"] = deepseek_model
            deepseek_base_url = settings.DEEPSEEK_API_BASE.rstrip('/')
            if not deepseek_base_url.endswith("/v1"):
                if "/v1" not in deepseek_base_url:
                    deepseek_base_url = f"{deepseek_base_url}/v1"
            os.environ["OPENAI_BASE_URL"] = deepseek_base_url
            os.environ["LLM_ENDPOINT"] = deepseek_base_url
            # litellm 可能需要这个
            os.environ["LITELLM_API_BASE"] = deepseek_base_url
            logger.info(f"Cognee 使用 DeepSeek: {deepseek_model} @ {deepseek_base_url}")
            
            # 通过 Cognee 配置 API 设置 LLM 配置（确保 Cognee 能正确读取）
            try:
                from cognee.infrastructure.llm import get_llm_config
                from cognee.modules.settings.save_llm_config import save_llm_config, LLMConfig
                get_llm_config.cache_clear()
                llm_config_obj = LLMConfig(
                    provider="openai",
                    model=deepseek_model,
                    api_key=settings.DEEPSEEK_API_KEY
                )
                await save_llm_config(llm_config_obj)
                fresh_config = get_llm_config()
                fresh_config.llm_endpoint = deepseek_base_url
                fresh_config.llm_api_key = settings.DEEPSEEK_API_KEY
                fresh_config.llm_model = deepseek_model
                logger.info(f"✅ DeepSeek 配置已通过 save_llm_config 设置: model={deepseek_model}")
            except Exception as e:
                logger.warning(f"⚠️ 通过 save_llm_config 设置 DeepSeek 配置失败: {e}，将仅使用环境变量")
        elif provider == "qwen" or provider == "qianwen":
            if not settings.QWEN_API_KEY:
                raise ValueError("Qwen API key not configured")
            os.environ["LLM_API_KEY"] = settings.QWEN_API_KEY
            os.environ["OPENAI_API_KEY"] = settings.QWEN_API_KEY
            # Cognee/litellm 可能也需要这些环境变量
            os.environ["LITELLM_API_KEY"] = settings.QWEN_API_KEY
            os.environ["LLM_PROVIDER"] = "openai"
            # litellm 需要格式：openai/model_name
            qwen_model = f"openai/{settings.QWEN_MODEL}" if not settings.QWEN_MODEL.startswith("openai/") else settings.QWEN_MODEL
            os.environ["LLM_MODEL"] = qwen_model
            qwen_base_url = settings.QWEN_API_BASE.rstrip('/')
            if "/compatible-mode/v1" not in qwen_base_url:
                if "/compatible-mode" not in qwen_base_url:
                    qwen_base_url = f"{qwen_base_url}/compatible-mode/v1"
                else:
                    if not qwen_base_url.endswith("/v1"):
                        qwen_base_url = f"{qwen_base_url}/v1"
            os.environ["OPENAI_BASE_URL"] = qwen_base_url
            os.environ["LLM_ENDPOINT"] = qwen_base_url
            # litellm 可能需要这个
            os.environ["LITELLM_API_BASE"] = qwen_base_url
            logger.info(f"Cognee 使用 Qwen: {qwen_model} @ {qwen_base_url}")
            
            # 通过 Cognee 配置 API 设置 LLM 配置（确保 Cognee 能正确读取）
            try:
                from cognee.infrastructure.llm import get_llm_config
                from cognee.modules.settings.save_llm_config import save_llm_config, LLMConfig
                get_llm_config.cache_clear()
                llm_config_obj = LLMConfig(
                    provider="openai",
                    model=qwen_model,
                    api_key=settings.QWEN_API_KEY
                )
                await save_llm_config(llm_config_obj)
                fresh_config = get_llm_config()
                fresh_config.llm_endpoint = qwen_base_url
                fresh_config.llm_api_key = settings.QWEN_API_KEY
                fresh_config.llm_model = qwen_model
                logger.info(f"✅ Qwen 配置已通过 save_llm_config 设置: model={qwen_model}")
            except Exception as e:
                logger.warning(f"⚠️ 通过 save_llm_config 设置 Qwen 配置失败: {e}，将仅使用环境变量")
        elif provider == "kimi":
            if not settings.KIMI_API_KEY:
                raise ValueError("Kimi API key not configured")
            os.environ["LLM_API_KEY"] = settings.KIMI_API_KEY
            os.environ["OPENAI_API_KEY"] = settings.KIMI_API_KEY
            # Cognee/litellm 可能也需要这些环境变量
            os.environ["LITELLM_API_KEY"] = settings.KIMI_API_KEY
            os.environ["LLM_PROVIDER"] = "openai"
            # litellm 需要格式：openai/model_name
            kimi_model = f"openai/{settings.KIMI_MODEL}" if not settings.KIMI_MODEL.startswith("openai/") else settings.KIMI_MODEL
            os.environ["LLM_MODEL"] = kimi_model
            kimi_base_url = settings.KIMI_API_BASE.rstrip('/')
            if not kimi_base_url.endswith("/v1"):
                if "/v1" not in kimi_base_url:
                    kimi_base_url = f"{kimi_base_url}/v1"
            os.environ["OPENAI_BASE_URL"] = kimi_base_url
            os.environ["LLM_ENDPOINT"] = kimi_base_url
            # litellm 可能需要这个
            os.environ["LITELLM_API_BASE"] = kimi_base_url
            logger.info(f"Cognee 使用 Kimi: {kimi_model} @ {kimi_base_url}")
            
            # 通过 Cognee 配置 API 设置 LLM 配置（确保 Cognee 能正确读取）
            try:
                from cognee.infrastructure.llm import get_llm_config
                from cognee.modules.settings.save_llm_config import save_llm_config, LLMConfig
                get_llm_config.cache_clear()
                llm_config_obj = LLMConfig(
                    provider="openai",
                    model=kimi_model,
                    api_key=settings.KIMI_API_KEY
                )
                await save_llm_config(llm_config_obj)
                fresh_config = get_llm_config()
                fresh_config.llm_endpoint = kimi_base_url
                fresh_config.llm_api_key = settings.KIMI_API_KEY
                fresh_config.llm_model = kimi_model
                logger.info(f"✅ Kimi 配置已通过 save_llm_config 设置: model={kimi_model}")
            except Exception as e:
                logger.warning(f"⚠️ 通过 save_llm_config 设置 Kimi 配置失败: {e}，将仅使用环境变量")
        elif provider == "local":
            if hasattr(settings, 'LOCAL_LLM_API_KEY') and settings.LOCAL_LLM_API_KEY:
                # 强制设置所有必要的环境变量
                os.environ["LLM_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["OPENAI_API_KEY"] = settings.LOCAL_LLM_API_KEY
                
                # 设置 LLM provider 和 model
                os.environ["LLM_PROVIDER"] = "openai"
                if hasattr(settings, 'LOCAL_LLM_MODEL') and settings.LOCAL_LLM_MODEL:
                    model_name = settings.LOCAL_LLM_MODEL
                    # 修复：如果模型路径是完整路径（以 / 开头），保留完整路径
                    # 设置成 openai//home/llm_deploy/Qwen3-32B（双斜杠）
                    # 这样 litellm 去掉 openai/ 前缀后会得到正确的 /home/llm_deploy/Qwen3-32B
                    if model_name.startswith('/'):
                        # 完整路径，保留原样，设置成 openai//path（双斜杠）
                        os.environ["LLM_MODEL"] = f"openai/{model_name}"
                    elif '/' in model_name and not model_name.startswith('openai/'):
                        # 非完整路径但包含斜杠，只取最后一部分（这是原来的逻辑）
                        model_name = model_name.split('/')[-1]
                        os.environ["LLM_MODEL"] = f"openai/{model_name}"
                    elif not model_name.startswith('openai/'):
                        # 只是模型名，直接使用
                        os.environ["LLM_MODEL"] = f"openai/{model_name}"
                    else:
                        # 已经是 openai/ 格式，直接使用
                        os.environ["LLM_MODEL"] = model_name
                else:
                    os.environ["LLM_MODEL"] = "openai/gpt-4"
                
                # 设置 endpoint
                if hasattr(settings, 'LOCAL_LLM_API_BASE_URL') and settings.LOCAL_LLM_API_BASE_URL:
                    local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
                    if not local_base_url.endswith('/v1'):
                        if '/v1' not in local_base_url:
                            local_base_url = f"{local_base_url}/v1"
                    os.environ["OPENAI_BASE_URL"] = local_base_url
                    os.environ["LLM_ENDPOINT"] = local_base_url
                logger.info(f"Cognee 使用本地大模型: {os.environ.get('LLM_MODEL')} @ {os.environ.get('OPENAI_BASE_URL', 'N/A')}")
            else:
                raise ValueError("本地大模型配置未设置")
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        logger.debug(
            f"Cognee LLM 环境变量已设置: "
            f"LLM_API_KEY={'SET' if os.environ.get('LLM_API_KEY') else 'NOT SET'}, "
            f"LLM_PROVIDER={os.environ.get('LLM_PROVIDER')}, "
            f"LLM_MODEL={os.environ.get('LLM_MODEL')}, "
            f"LLM_ENDPOINT={os.environ.get('LLM_ENDPOINT')}"
        )
        
        # 获取阈值配置
        threshold = getattr(settings, 'COGNEE_SECTION_TEMPLATE_THRESHOLD', 5)
        section_count = len(sections)
        
        logger.info(f"开始使用 Cognee 为 {section_count} 个章节构建知识图谱（阈值: {threshold}）")
        
        # 准备数据库配置
        # 注意：Cognee 的 config 参数格式可能与我们的预期不同，传递字典可能导致参数不匹配
        # 由于我们已经在 get_cognee() 中设置了所有必要的环境变量，这里传递 None 让 Cognee 使用环境变量
        # 这样可以避免参数不匹配的问题（如缺少 vector_db_name、graph_db_provider 格式错误等）
        graph_db_config = None
        vector_db_config = None
        
        # 记录配置状态（用于调试）
        if hasattr(settings, 'ENABLE_MILVUS') and settings.ENABLE_MILVUS:
            if hasattr(settings, 'MILVUS_HOST') and settings.MILVUS_HOST:
                logger.info(f"Milvus 已启用，Cognee 将使用环境变量中的 Milvus 配置（vector_db_config=None）")
            else:
                logger.warning("MILVUS_HOST 未设置，vector_db_config 为 None")
        else:
            logger.info("ENABLE_MILVUS 未启用，vector_db_config 为 None（将使用默认 LanceDB）")
        
        logger.info(f"Cognee 将使用环境变量中的 Neo4j 配置（graph_db_config=None）")
        
        # 关键修复：每次处理生成唯一的 dataset_name，但 group_id 保持不变
        # 这样同一份文档可以多次处理，每次都是新的 dataset，不会冲突
        import time
        import uuid
        timestamp = int(time.time() * 1000)  # 毫秒级时间戳
        unique_id = str(uuid.uuid4())[:8]  # 8位 UUID 作为额外唯一标识
        dataset_name = f"knowledge_base_{group_id}_{timestamp}_{unique_id}"
        logger.info(f"生成唯一的 dataset_name: {dataset_name} (group_id: {group_id})")
        
        results = {
            "total": section_count,
            "success": 0,
            "failed": 0,
            "section_data": []
        }
        
        # 先批量添加所有章节内容
        # 根据确认的方案：智能分块产生的chunks对应DataNode，每个chunk的content来自chunks.json
        section_texts = []
        section_metadata = []
        
        logger.info(
            f"准备 {len(sections)} 个章节数据（来自智能分块的chunks.json），"
            f"每个章节将作为DataNode/TextDocument添加到Cognee"
        )
        
        for idx, section in enumerate(sections):
            section_title = section.get("title", f"章节_{idx+1}")
            section_content = section.get("content", "")
            section_uuid = section.get("uuid")
            
            if not section_content.strip():
                logger.warning(f"章节 '{section_title}' 内容为空，跳过")
                continue
            
            # 验证内容长度（DataNode受max_tokens_per_section限制，但这里已经分块完成）
            content_length = len(section_content)
            logger.debug(
                f"章节[{idx+1}] '{section_title}': "
                f"内容长度={content_length} 字符, uuid={section_uuid}"
            )
            
            section_texts.append(section_content)
            section_metadata.append({
                "title": section_title,
                "section_uuid": section_uuid,
                "group_id": group_id,
                "index": idx,
                "content_length": content_length
            })
        
        if not section_texts:
            logger.warning("没有有效的章节内容，跳过知识图谱构建")
            return {"success": False, "reason": "no_valid_sections"}
        
        try:
            # 注意：不再需要清除逻辑，因为每次处理都使用唯一的 dataset_name
            # 这样每次都是全新的 dataset，不会与之前的处理冲突
            logger.info(f"开始处理 dataset '{dataset_name}' (group_id: {group_id})")
            
            # 直接开始处理，不需要清除（每次都是新的 dataset）
            
            # 1. 批量添加章节内容到 Cognee
            # 根据确认的方案：智能分块产生的chunks对应DataNode，Cognee会自动创建DocumentChunk
            logger.info(
                f"添加 {len(section_texts)} 个章节到 Cognee dataset: {dataset_name} "
                f"(每个章节对应一个DataNode/TextDocument，Cognee会自动创建DocumentChunk)"
            )
            # 不传递 vector_db_config 和 graph_db_config，让 Cognee 使用环境变量
            try:
                add_result = await self.cognee.add(
                    section_texts,
                    dataset_name=dataset_name
                )
                logger.info(f"✅ add() 执行完成，返回值: {add_result}")
                
                # 验证层级关系：TextDocument -> DataNode -> DocumentChunk
                from app.core.neo4j_client import neo4j_client
                
                # 检查 add() 是否在 Neo4j 中创建了节点
                check_add_nodes_query = """
                MATCH (n)
                WHERE '__Node__' IN labels(n)
                   OR 'DataNode' IN labels(n)
                   OR 'TextDocument' IN labels(n)
                   OR 'DocumentChunk' IN labels(n)
                   OR 'Chunk' IN labels(n)
                   OR 'Entity' IN labels(n)
                   OR 'EntityType' IN labels(n)
                   OR 'TextSummary' IN labels(n)
                RETURN count(n) as node_count
                """
                check_add_result = neo4j_client.execute_query(check_add_nodes_query)
                add_node_count = check_add_result[0]["node_count"] if check_add_result else 0
                logger.info(f"✅ add() 后在 Neo4j 中创建了 {add_node_count} 个节点")
                
                # 验证层级关系：TextDocument/DataNode -> DocumentChunk
                hierarchy_check_query = """
                MATCH (td)
                WHERE ('TextDocument' IN labels(td) OR 'DataNode' IN labels(td))
                  AND (td.dataset_name = $dataset_name OR td.dataset_id = $dataset_name)
                WITH td
                OPTIONAL MATCH (td)<-[:is_part_of]-(dc)
                WHERE 'DocumentChunk' IN labels(dc) OR 'Chunk' IN labels(dc)
                RETURN 
                    count(DISTINCT td) as text_document_count,
                    count(DISTINCT dc) as document_chunk_count
                """
                hierarchy_result = neo4j_client.execute_query(hierarchy_check_query, {
                    "dataset_name": dataset_name
                })
                
                if hierarchy_result:
                    td_count = hierarchy_result[0].get("text_document_count", 0)
                    dc_count = hierarchy_result[0].get("document_chunk_count", 0)
                    logger.info(
                        f"✅ 层级关系验证: TextDocument/DataNode={td_count} 个, "
                        f"DocumentChunk={dc_count} 个 "
                        f"(预期: TextDocument/DataNode={len(section_texts)} 个, DocumentChunk由Cognee自动创建)"
                    )
                    
                    # 验证：每个TextDocument/DataNode应该对应多个DocumentChunk（Cognee自动分块）
                    if td_count > 0 and dc_count == 0:
                        logger.warning(
                            f"⚠️ 检测到 {td_count} 个 TextDocument/DataNode，但没有 DocumentChunk。"
                            f"这可能表示Cognee尚未完成分块，或者配置有问题。"
                        )
                    elif td_count == 0:
                        logger.warning(
                            f"⚠️ 未检测到 TextDocument/DataNode 节点。"
                            f"这可能表示Cognee尚未创建节点，或者dataset_name不匹配。"
                        )
                else:
                    logger.warning("⚠️ 层级关系验证查询返回空结果")
                
                if add_node_count == 0:
                    logger.warning(f"⚠️ add() 执行完成，但 Neo4j 中没有创建任何节点！这可能是配置问题。")
            except Exception as e:
                logger.error(f"❌ add() 执行失败: {e}", exc_info=True)
                raise
            
            # 2. 根据配置模式选择模板生成方案
            custom_prompt = None
            
            # 检查是否使用JSON配置
            if cognify_template_mode == "json_config" and cognify_template_config_json:
                logger.info(f"使用JSON配置模式生成模板")
                # 直接使用JSON配置转换为 custom_prompt
                custom_prompt = self._template_to_custom_prompt(cognify_template_config_json)
                logger.info(f"✅ 已使用JSON配置生成模板，包含 {len(cognify_template_config_json.get('entity_types', {}))} 个实体类型")
                
                # 保存模板到数据库（如果提供了upload_id）
                if upload_id and document_name:
                    template_id = await self._save_cognee_template_to_db(
                        template_config=cognify_template_config_json,
                        upload_id=upload_id,
                        document_name=document_name,
                        section_count=section_count,
                        template_type="JSON配置",
                        provider=provider
                    )
                    if template_id:
                        logger.info(f"✅ Cognee 模板保存成功，template_id={template_id}")
            elif section_count < threshold:
                # 方案2：为每个章节单独生成模板（章节数量少）
                logger.info(f"章节数量 {section_count} < 阈值 {threshold}，使用方案2：为每个章节单独生成模板")
                
                # 合并所有章节内容，生成一个综合模板
                # 注意：虽然是为每个章节生成，但 Cognee 的 cognify 是对整个 dataset 操作的
                # 所以我们合并所有章节内容生成一个模板，用于整个 dataset
                all_sections_content = "\n\n".join([
                    f"## {meta['title']}\n{section_texts[i]}"
                    for i, meta in enumerate(section_metadata)
                ])
                
                # 生成模板
                template_config = await self._generate_section_template(
                    section_content=all_sections_content,
                    section_title=f"所有章节（共{section_count}个）",
                    provider=provider
                )
                
                # 转换为 custom_prompt
                custom_prompt = self._template_to_custom_prompt(template_config)
                logger.info(f"方案2：已生成章节级别模板，包含 {len(template_config.get('entity_types', {}))} 个实体类型")
                
                # 保存模板到数据库
                logger.info(f"准备保存 Cognee 模板到数据库: upload_id={upload_id}, document_name={document_name}, section_count={section_count}")
                if upload_id and document_name:
                    template_id = await self._save_cognee_template_to_db(
                        template_config=template_config,
                        upload_id=upload_id,
                        document_name=document_name,
                        section_count=section_count,
                        template_type="方案2-章节级别",
                        provider=provider
                    )
                    if template_id:
                        logger.info(f"✅ Cognee 模板保存成功，template_id={template_id}")
                    else:
                        logger.warning(f"⚠️ Cognee 模板保存失败（返回 None）")
                else:
                    logger.warning(f"⚠️ 跳过 Cognee 模板保存: upload_id={upload_id}, document_name={document_name}")
                
            else:
                # 方案1：为所有章节生成一个模板（章节数量多）
                logger.info(f"章节数量 {section_count} >= 阈值 {threshold}，使用方案1：为所有章节生成一个模板")
                
                # 合并所有章节内容
                all_sections_content = "\n\n".join([
                    f"## {meta['title']}\n{section_texts[i]}"
                    for i, meta in enumerate(section_metadata)
                ])
                
                # 生成模板
                template_config = await self._generate_section_template(
                    section_content=all_sections_content,
                    section_title=f"所有章节（共{section_count}个）",
                    provider=provider
                )
                
                # 转换为 custom_prompt
                custom_prompt = self._template_to_custom_prompt(template_config)
                logger.info(f"方案1：已生成统一模板，包含 {len(template_config.get('entity_types', {}))} 个实体类型")
                
                # 保存模板到数据库
                logger.info(f"准备保存 Cognee 模板到数据库: upload_id={upload_id}, document_name={document_name}, section_count={section_count}")
                if upload_id and document_name:
                    template_id = await self._save_cognee_template_to_db(
                        template_config=template_config,
                        upload_id=upload_id,
                        document_name=document_name,
                        section_count=section_count,
                        template_type="方案1-统一模板",
                        provider=provider
                    )
                    if template_id:
                        logger.info(f"✅ Cognee 模板保存成功，template_id={template_id}")
                    else:
                        logger.warning(f"⚠️ Cognee 模板保存失败（返回 None）")
                else:
                    logger.warning(f"⚠️ 跳过 Cognee 模板保存: upload_id={upload_id}, document_name={document_name}")
            
            # 3. Cognify: 为整个 dataset 生成知识图谱（使用 custom_prompt）
            logger.info(f"开始为 dataset '{dataset_name}' 构建知识图谱（使用自定义模板）")
            # 不传递 vector_db_config 和 graph_db_config，让 Cognee 使用环境变量
            try:
                await self.cognee.cognify(
                    datasets=dataset_name,
                    custom_prompt=custom_prompt  # 传递自定义模板
                )
            except Exception as cognify_error:
                # 检查是否是 Milvus 向量为 nil 的错误
                error_str = str(cognify_error)
                if "nil" in error_str.lower() or "vector" in error_str.lower() and "illegal" in error_str.lower():
                    logger.warning(f"⚠️ cognify() 遇到向量为 nil 的错误（可能是某些数据点没有有效文本）: {cognify_error}")
                    logger.warning(f"⚠️ 这通常不影响知识图谱的核心功能（Neo4j 节点和关系可能已创建）")
                    # 继续执行，不中断流程
                else:
                    # 其他错误，重新抛出
                    raise
            
            # 检查 cognify() 是否成功创建了节点
            # Cognee 实际创建的节点类型：Entity, DocumentChunk, TextDocument, EntityType, TextSummary（都有 __Node__ 标签）
            from app.core.neo4j_client import neo4j_client
            check_nodes_query = """
            MATCH (n)
            WHERE '__Node__' IN labels(n)
               AND ('Entity' IN labels(n) 
               OR 'DocumentChunk' IN labels(n)
               OR 'TextDocument' IN labels(n)
               OR 'EntityType' IN labels(n)
               OR 'TextSummary' IN labels(n)
               OR 'KnowledgeNode' IN labels(n))
            RETURN count(n) as node_count
            """
            check_result = neo4j_client.execute_query(check_nodes_query)
            node_count = check_result[0]["node_count"] if check_result else 0
            
            if node_count == 0:
                logger.warning(
                    f"⚠️ cognify() 完成后，Neo4j 中仍然没有节点。"
                    f"这可能是因为 Cognee 认为 dataset '{dataset_name}' 已经处理过，跳过了知识提取。"
                    f"尝试清除 Cognee 的 pipeline runs 并重试..."
                )
                
                # 尝试清除 Cognee 的 pipeline runs 并重试
                try:
                    from cognee.infrastructure.databases.relational import get_relational_engine
                    from cognee.modules.pipelines.models import PipelineRun
                    from cognee.modules.data.models import Dataset
                    from sqlalchemy import select, delete
                    
                    engine = get_relational_engine()
                    deleted_count = 0
                    
                    # 通过 dataset_name 查找 dataset_id
                    async with engine.get_async_session() as session:
                        query = select(Dataset).filter(Dataset.name == dataset_name)
                        datasets = (await session.execute(query)).scalars().all()
                        
                        if datasets:
                            for dataset in datasets:
                                dataset_id = dataset.id
                                logger.info(f"找到 dataset ID: {dataset_id}，清除其 pipeline runs...")
                                
                                # 删除所有相关的 pipeline runs
                                delete_query = delete(PipelineRun).filter(PipelineRun.dataset_id == dataset_id)
                                result = await session.execute(delete_query)
                                await session.commit()
                                
                                deleted_count = result.rowcount
                                logger.info(f"✅ 清除了 {deleted_count} 个 pipeline runs")
                        else:
                            logger.warning(f"未找到 dataset: {dataset_name}，无法清除 pipeline runs")
                    
                    # 如果成功清除了 pipeline runs，重试 cognify()
                    if deleted_count > 0:
                        logger.info(f"重试 cognify()...")
                        await self.cognee.cognify(
                            datasets=dataset_name,
                            custom_prompt=custom_prompt
                        )
                        
                        # 再次检查节点数量
                        check_result = neo4j_client.execute_query(check_nodes_query)
                        node_count = check_result[0]["node_count"] if check_result else 0
                        
                        if node_count > 0:
                            logger.info(f"✅ 重试成功！cognify() 创建了 {node_count} 个节点")
                        else:
                            logger.warning(f"⚠️ 重试后仍然没有创建节点")
                            
                except Exception as e:
                    logger.error(f"清除 pipeline runs 并重试失败: {e}", exc_info=True)
            else:
                logger.info(f"✅ cognify() 成功创建了 {node_count} 个节点")
            
            # 4. Memify: 添加记忆算法到图谱
            # ========== 关键修复：解决 @lru_cache + Pipeline 多进程配置传递问题 ==========
            # 问题本质：get_llm_config() 使用 @lru_cache，在 Pipeline Task 多进程执行时，
            # 子进程第一次调用会缓存"空配置"，导致后续配置无法传递
            # 
            # 解决方案（采用 GPT 建议的方案三 + 方案二组合）：
            # 1. 方案三：环境变量兜底（最稳定，子进程一定能拿到）
            # 2. 方案二：显式清空缓存 + 重新设置配置
            
            if hasattr(settings, 'LOCAL_LLM_API_KEY') and settings.LOCAL_LLM_API_KEY:
                import os
                import litellm
                
                # ========== 关键修复：禁用 litellm 的 aiohttp 传输，改用 httpx ==========
                # 问题：litellm 使用 aiohttp 时出现 "Server disconnected" 错误
                # 原因：LLM 服务对 aiohttp 的异步连接处理有问题
                # 解决：禁用 aiohttp，改用 httpx（更稳定）
                try:
                    # 关键1：删除已缓存的 aiohttp handler
                    if hasattr(litellm, 'base_llm_aiohttp_handler'):
                        litellm.base_llm_aiohttp_handler = None
                        logger.info("✅ 已删除 litellm.base_llm_aiohttp_handler")
                    
                    # 关键2：设置配置标志
                    litellm.disable_aiohttp_transport = True
                    litellm.use_aiohttp_transport = False
                    logger.info("✅ 已禁用 litellm 的 aiohttp 传输，改用 httpx")
                except Exception as e:
                    logger.warning(f"⚠️ 无法禁用 aiohttp 传输: {e}")
                
                # ========== 步骤1：设置环境变量（方案三：环境变量兜底）==========
                # 这是最稳定的方案，因为子进程一定能拿到环境变量
                os.environ["LLM_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["OPENAI_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["LLM_PROVIDER"] = "openai"
                
                # 设置 LLM 请求超时时间
                timeout_seconds = getattr(settings, 'COGNEE_LLM_REQUEST_TIMEOUT', 600.0)
                os.environ["LITELLM_REQUEST_TIMEOUT"] = str(timeout_seconds)
                
                if hasattr(settings, 'LOCAL_LLM_API_BASE_URL') and settings.LOCAL_LLM_API_BASE_URL:
                    local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
                    if not local_base_url.endswith('/v1'):
                        if '/v1' not in local_base_url:
                            local_base_url = f"{local_base_url}/v1"
                    os.environ["OPENAI_BASE_URL"] = local_base_url
                    os.environ["LLM_ENDPOINT"] = local_base_url
                    
                    if hasattr(settings, 'LOCAL_LLM_MODEL') and settings.LOCAL_LLM_MODEL:
                        model_name = settings.LOCAL_LLM_MODEL
                        if model_name.startswith('/'):
                            litellm_model = f"openai/{model_name}"
                        else:
                            litellm_model = f"openai/{model_name}"
                    else:
                        litellm_model = "openai/gpt-4"
                    
                    os.environ["LLM_MODEL"] = litellm_model
                    os.environ["LITELLM_MODEL"] = litellm_model  # LiteLLM 也认这个变量
                    
                    logger.info(f"✅ 环境变量已设置（方案三：环境变量兜底）: LLM_MODEL={litellm_model}, OPENAI_BASE_URL={local_base_url}, LITELLM_REQUEST_TIMEOUT={timeout_seconds}")
                    
                    # ========== 步骤2：清空缓存 + 重新设置配置（方案二）==========
                    # 关键：必须在设置环境变量后，再清空缓存，然后重新设置配置
                    try:
                        from cognee.infrastructure.llm import get_llm_config
                        from cognee.modules.settings.save_llm_config import save_llm_config, LLMConfig
                        
                        # 清空缓存（方案二：显式清空缓存）
                        get_llm_config.cache_clear()
                        logger.info("✅ 已清除 get_llm_config 缓存（方案二：显式清空缓存）")
                        
                        # 重新设置配置（此时环境变量已设置，get_llm_config() 会读取到正确的值）
                        llm_config_obj = LLMConfig(
                            provider="openai",
                            model=litellm_model,
                            api_key=settings.LOCAL_LLM_API_KEY
                        )
                        await save_llm_config(llm_config_obj)
                        
                        # 手动设置 llm_endpoint（save_llm_config 不会设置）
                        fresh_config = get_llm_config()
                        fresh_config.llm_endpoint = local_base_url
                        fresh_config.llm_api_key = settings.LOCAL_LLM_API_KEY  # 确保设置
                        fresh_config.llm_model = litellm_model  # 确保设置
                        
                        logger.info(f"✅ 配置已重新设置: llm_model={fresh_config.llm_model}, llm_endpoint={fresh_config.llm_endpoint}, llm_api_key={'已设置' if fresh_config.llm_api_key else '未设置'}")
                    except Exception as e:
                        logger.warning(f"⚠️ 清空缓存或重新设置配置失败: {e}")
                        logger.warning("⚠️ 将继续使用环境变量（方案三），这应该足够稳定")
                        import traceback
                        logger.debug(f"配置设置错误详情: {traceback.format_exc()}")
                
                logger.info(f"memify() 调用前配置检查完成 - 环境变量已设置，缓存已清除，配置已更新")
            
            logger.info(f"为 dataset '{dataset_name}' 添加记忆算法")
            try:
                # 检查是否使用JSON配置
                if memify_template_mode == "json_config" and memify_template_config_json:
                    logger.info(f"使用JSON配置模式执行 memify()")
                    # 解析JSON配置
                    extraction_config = memify_template_config_json.get("extraction", {})
                    enrichment_config = memify_template_config_json.get("enrichment", {})
                    
                    extraction_enabled = extraction_config.get("enabled", True)
                    enrichment_enabled = enrichment_config.get("enabled", True)
                    
                    extraction_tasks_list = []
                    enrichment_tasks_list = []
                    
                    # 构建 extraction_tasks
                    if extraction_enabled:
                        try:
                            from cognee.modules.pipelines.tasks.task import Task
                            from cognee.tasks.memify.extract_subgraph_chunks import extract_subgraph_chunks
                            
                            extraction_task = Task(extract_subgraph_chunks)
                            extraction_tasks_list.append(extraction_task)
                            logger.info(f"✅ extraction_task 创建成功（JSON配置）")
                        except ImportError as e:
                            logger.warning(f"⚠️ 无法导入 extraction 相关函数: {e}")
                    
                    # 构建 enrichment_tasks
                    if enrichment_enabled:
                        try:
                            from cognee.modules.pipelines.tasks.task import Task
                            from app.utils.cognee_task_wrapper import wrap_add_rule_associations
                            
                            # 获取配置参数
                            rules_nodeset_name = enrichment_config.get("rules_nodeset_name", "default_rules")
                            user_prompt_location = enrichment_config.get("user_prompt_location", "coding_rule_association_agent_user.txt")
                            system_prompt_location = enrichment_config.get("system_prompt_location", "coding_rule_association_agent_system.txt")
                            
                            # 创建包装函数，传入配置参数
                            wrapped_func = wrap_add_rule_associations()
                            
                            # 创建一个新的包装函数，传入配置参数
                            async def configured_wrapper(*args, **kwargs):
                                # 如果kwargs中没有这些参数，则使用配置的值
                                if "rules_nodeset_name" not in kwargs:
                                    kwargs["rules_nodeset_name"] = rules_nodeset_name
                                if "user_prompt_location" not in kwargs:
                                    kwargs["user_prompt_location"] = user_prompt_location
                                if "system_prompt_location" not in kwargs:
                                    kwargs["system_prompt_location"] = system_prompt_location
                                return await wrapped_func(*args, **kwargs)
                            
                            enrichment_task = Task(configured_wrapper)
                            enrichment_tasks_list.append(enrichment_task)
                            logger.info(f"✅ enrichment_task 创建成功（JSON配置: rules_nodeset_name={rules_nodeset_name}）")
                            
                            # 应用 add_rule_associations monkey patch
                            try:
                                from app.utils.patch_add_rule_associations import apply_patch
                                if apply_patch():
                                    logger.info("✅ 已应用 add_rule_associations patch（使用简单 BaseModel）")
                            except Exception as patch_error:
                                logger.warning(f"⚠️ 应用 add_rule_associations patch 失败: {patch_error}")
                        except ImportError as e:
                            logger.warning(f"⚠️ 无法导入 enrichment 相关函数: {e}")
                    
                    # 执行 memify()
                    if extraction_tasks_list or enrichment_tasks_list:
                        await self.cognee.memify(
                            dataset=dataset_name,
                            extraction_tasks=extraction_tasks_list if extraction_tasks_list else None,
                            enrichment_tasks=enrichment_tasks_list if enrichment_tasks_list else None,
                        )
                        logger.info(f"✅ memify() 执行完成（JSON配置: extraction={extraction_enabled}, enrichment={enrichment_enabled}）")
                        
                        # 保存Memify模板到数据库（JSON配置）
                        if upload_id and document_name:
                            template_id = await self._save_memify_template_to_db(
                                memify_config=memify_template_config_json,
                                upload_id=upload_id,
                                document_name=document_name,
                                dataset_name=dataset_name,
                                memify_template_mode=memify_template_mode,
                                provider=provider
                            )
                            if template_id:
                                logger.info(f"✅ Memify 模板保存成功，template_id={template_id}")
                    else:
                        logger.warning("⚠️ extraction 和 enrichment 都被禁用，跳过 memify()")
                else:
                    # 使用LLM自动生成配置（使用默认任务，add_rule_associations内部会调用LLM生成规则）
                    logger.info(f"使用LLM自动生成配置执行 memify()")
                    try:
                        from cognee.modules.pipelines.tasks.task import Task
                        from cognee.tasks.memify.extract_subgraph_chunks import extract_subgraph_chunks
                        from cognee.tasks.codingagents.coding_rule_associations import add_rule_associations
                        from app.utils.cognee_task_wrapper import wrap_add_rule_associations
                        logger.info(f"✅ 成功导入 Task 和相关函数")
                        
                        extraction_task = Task(extract_subgraph_chunks)
                        logger.info(f"✅ extraction_task 创建成功")
                        
                        wrapped_add_rule_associations = wrap_add_rule_associations()
                        enrichment_task = Task(wrapped_add_rule_associations)
                        logger.info(f"✅ enrichment_task 创建成功（已包装，确保配置正确）")
                        
                        # 应用 add_rule_associations monkey patch
                        try:
                            from app.utils.patch_add_rule_associations import apply_patch
                            if apply_patch():
                                logger.info("✅ 已应用 add_rule_associations patch（使用简单 BaseModel）")
                        except Exception as patch_error:
                            logger.warning(f"⚠️ 应用 add_rule_associations patch 失败: {patch_error}")
                        
                        logger.info(f"✅ 使用优化的 memify() 配置: 限制 extraction_tasks 和 enrichment_tasks, dataset={dataset_name}")
                        
                        await self.cognee.memify(
                            dataset=dataset_name,
                            extraction_tasks=[extraction_task],
                            enrichment_tasks=[enrichment_task],
                        )
                        logger.info(f"✅ memify() 执行完成（使用LLM自动生成配置）")
                        
                        # 保存Memify模板到数据库
                        if upload_id and document_name:
                            memify_config = {
                                "extraction": {
                                    "enabled": True,
                                    "task": "extract_subgraph_chunks"
                                },
                                "enrichment": {
                                    "enabled": True,
                                    "task": "add_rule_associations",
                                    "rules_nodeset_name": "default_rules"
                                }
                            }
                            template_id = await self._save_memify_template_to_db(
                                memify_config=memify_config,
                                upload_id=upload_id,
                                document_name=document_name,
                                dataset_name=dataset_name,
                                memify_template_mode=memify_template_mode,
                                provider=provider
                            )
                            if template_id:
                                logger.info(f"✅ Memify 模板保存成功，template_id={template_id}")
                    except ImportError as import_error:
                        logger.warning(f"⚠️ 无法导入 Task 或相关函数，使用默认 memify() 调用: {import_error}")
                        await self.cognee.memify()
                        logger.info(f"✅ memify() 执行完成（使用LLM自动生成配置）")
                        
                        # 保存Memify模板到数据库（默认配置）
                        if upload_id and document_name:
                            memify_config = {
                                "extraction": {
                                    "enabled": True,
                                    "task": "extract_subgraph_chunks"
                                },
                                "enrichment": {
                                    "enabled": True,
                                    "task": "add_rule_associations",
                                    "rules_nodeset_name": "default_rules"
                                }
                            }
                            template_id = await self._save_memify_template_to_db(
                                memify_config=memify_config,
                                upload_id=upload_id,
                                document_name=document_name,
                                dataset_name=dataset_name,
                                memify_template_mode=memify_template_mode,
                                provider=provider
                            )
                            if template_id:
                                logger.info(f"✅ Memify 模板保存成功，template_id={template_id}")
                    except Exception as task_error:
                        logger.warning(f"⚠️ Task 创建失败，使用默认 memify() 调用: {task_error}")
                        await self.cognee.memify()
                        logger.info(f"✅ memify() 执行完成（使用LLM自动生成配置）")
                        
                        # 保存Memify模板到数据库（默认配置）
                        if upload_id and document_name:
                            memify_config = {
                                "extraction": {
                                    "enabled": True,
                                    "task": "extract_subgraph_chunks"
                                },
                                "enrichment": {
                                    "enabled": True,
                                    "task": "add_rule_associations",
                                    "rules_nodeset_name": "default_rules"
                            }
                            }
                            template_id = await self._save_memify_template_to_db(
                                memify_config=memify_config,
                                upload_id=upload_id,
                                document_name=document_name,
                                dataset_name=dataset_name,
                                memify_template_mode=memify_template_mode,
                                provider=provider
                            )
                            if template_id:
                                logger.info(f"✅ Memify 模板保存成功，template_id={template_id}")
            except Exception as memify_error:
                # memify() 失败不影响整体流程，记录错误但继续执行
                error_str = str(memify_error)
                if "Connection error" in error_str or "Connection" in error_str:
                    logger.warning(f"⚠️ memify() 执行失败（LLM 连接错误）: {memify_error}")
                    logger.warning(f"⚠️ 这通常不影响知识图谱的核心功能（Entity 和关系已由 cognify() 创建）")
                    logger.warning(f"⚠️ LLM 连接问题可能是临时的，可以稍后重试")
                else:
                    logger.warning(f"⚠️ memify() 执行失败（可能是 add_rule_associations 任务失败）: {memify_error}")
                    logger.warning(f"⚠️ 这通常不影响知识图谱的核心功能（Entity 和关系已由 cognify() 创建）")
            
            results["success"] = len(section_texts)
            results["section_data"] = [
                {
                    "section_uuid": meta.get("section_uuid"),
                    "title": meta.get("title"),
                    "index": meta.get("index")
                }
                for meta in section_metadata
            ]
            
            logger.info(
                f"Cognee 章节知识图谱构建完成: "
                f"总数={results['total']}, "
                f"成功={results['success']}, "
                f"失败={results['failed']}, "
                f"dataset={dataset_name}, "
                f"使用模板={'是' if custom_prompt else '否'}"
            )
            
            return {
                "success": True,
                "results": results,
                "dataset_name": dataset_name,
                "template_used": custom_prompt is not None
            }
            
        except Exception as e:
            logger.error(f"Cognee 章节知识图谱构建失败: {e}", exc_info=True)
            results["failed"] = len(section_texts)
            return {
                "success": False,
                "results": results,
                "error": str(e)
            }
    
    async def check_cognee_kg_exists(self, group_id: str) -> bool:
        """
        检查 Cognee 知识图谱是否存在
        
        Args:
            group_id: 文档组ID
            
        Returns:
            True 如果知识图谱存在，False 否则
        """
        from app.core.neo4j_client import neo4j_client
        
        try:
            # 使用 group_id 查询所有相关的节点（因为 dataset_name 每次都是唯一的）
            # Cognee 创建的节点可能有 group_id 属性，或者 dataset_name 包含 group_id
            query = """
            MATCH (n)
            WHERE '__Node__' IN labels(n)
               AND ('Entity' IN labels(n)
               OR 'DocumentChunk' IN labels(n)
               OR 'TextDocument' IN labels(n)
               OR 'EntityType' IN labels(n)
               OR 'TextSummary' IN labels(n)
               OR 'KnowledgeNode' IN labels(n))
               AND (
                   n.group_id = $group_id
                   OR (n.dataset_name IS NOT NULL AND n.dataset_name CONTAINS $group_id)
                   OR (n.dataset_id IS NOT NULL AND n.dataset_id CONTAINS $group_id)
               )
            RETURN count(n) as count
            LIMIT 1
            """
            
            result = neo4j_client.execute_query(query, {
                "group_id": group_id
            })
            
            if result and len(result) > 0:
                count = result[0].get("count", 0)
                exists = count > 0
                logger.debug(f"检查 Cognee 知识图谱: group_id={group_id}, 节点数={count}, 存在={exists}")
                return exists
            
            # 方法2：检查 Milvus 中是否有对应的 collection（更可靠的方法）
            # Cognee 使用 Milvus 时，会创建名为 {dataset_name}_text 的 collection
            try:
                from app.services.milvus_service import get_milvus_service
                milvus_service = get_milvus_service()
                
                if milvus_service.is_available():
                    # 检查 Milvus collection 是否存在
                    collection_name = f"{dataset_name}_text"
                    from pymilvus import utility
                    from app.core.config import settings
                    
                    # 获取 Milvus 连接别名
                    alias = "cognee_milvus"
                    
                    # 检查 collection 是否存在
                    collections = utility.list_collections(using=alias)
                    exists = collection_name in collections
                    
                    logger.debug(
                        f"检查 Milvus collection: collection_name={collection_name}, "
                        f"exists={exists}, all_collections={collections[:5]}..."
                    )
                    return exists
            except Exception as e:
                logger.warning(f"检查 Milvus collection 失败: {e}，回退到 Neo4j 检查结果")
            
            return False
            
        except Exception as e:
            logger.error(f"检查 Cognee 知识图谱是否存在时出错: {e}", exc_info=True)
            return False
    
    async def ensure_cognee_kg(
        self,
        group_id: str,
        upload_id: int = None,
        provider: str = "local"
    ) -> Dict[str, Any]:
        """
        确保 Cognee 知识图谱存在，不存在则创建（按需创建）
        
        这是两阶段检索策略的核心：
        - 第一次查询慢（需要构建知识图谱）
        - 之后查询快（复用已有知识图谱）
        
        Args:
            group_id: 文档组ID
            upload_id: 文档上传ID（可选，如果提供则从数据库读取章节数据）
            provider: LLM 提供商
            
        Returns:
            包含创建状态和统计信息的字典
        """
        import time
        from app.models.document_upload import DocumentUpload
        from app.core.mysql_client import SessionLocal
        
        start_time = time.time()
        dataset_name = f"knowledge_base_{group_id}"
        
        # 检查知识图谱是否已存在
        if await self.check_cognee_kg_exists(group_id):
            elapsed_time = time.time() - start_time
            logger.info(
                f"✅ Cognee 知识图谱已存在: dataset_name={dataset_name}, "
                f"检查耗时={elapsed_time:.2f}秒"
            )
            return {
                "exists": True,
                "created": False,
                "dataset_name": dataset_name,
                "check_time": elapsed_time,
                "build_time": 0
            }
        
        # 知识图谱不存在，需要创建
        logger.info(
            f"🔨 Cognee 知识图谱不存在，开始按需创建: "
            f"dataset_name={dataset_name}, group_id={group_id}"
        )
        
        build_start_time = time.time()
        
        # 如果没有提供 upload_id，尝试从 group_id 中提取
        if upload_id is None:
            # 尝试从 group_id 中提取 upload_id（格式：doc_123 或 upload_123）
            try:
                if group_id.startswith("doc_"):
                    upload_id = int(group_id.replace("doc_", ""))
                elif group_id.startswith("upload_"):
                    upload_id = int(group_id.replace("upload_", ""))
                else:
                    # 尝试从 group_id 末尾提取数字
                    import re
                    match = re.search(r'(\d+)$', group_id)
                    if match:
                        upload_id = int(match.group(1))
                    else:
                        raise ValueError(f"无法从 group_id 中提取 upload_id: {group_id}")
            except (ValueError, AttributeError) as e:
                logger.error(f"无法从 group_id 提取 upload_id: {e}")
            return {
                "exists": False,
                "created": False,
                "error": f"无法提取 upload_id: {e}",
                "group_id": group_id
            }
        
        # 从数据库读取文档和章节数据
        db = SessionLocal()
        try:
            document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if not document:
                raise ValueError(f"文档不存在: upload_id={upload_id}")
            
            # 检查是否有分块数据
            if not document.chunks_path or not os.path.exists(document.chunks_path):
                raise ValueError(f"文档尚未分块，无法创建知识图谱: upload_id={upload_id}")
            
            # 读取章节数据
            import json
            with open(document.chunks_path, 'r', encoding='utf-8') as f:
                chunks_data = json.load(f)
            
            chunks = chunks_data.get("chunks", [])
            if not chunks:
                raise ValueError(f"文档没有有效的章节数据: upload_id={upload_id}")
            
            logger.info(f"读取到 {len(chunks)} 个章节，开始构建知识图谱")
            
            # 准备章节数据
            sections = []
            for idx, chunk in enumerate(chunks):
                sections.append({
                    "title": chunk.get("title", f"章节_{idx+1}"),
                    "content": chunk.get("content", ""),
                    "uuid": chunk.get("uuid", f"{group_id}_chunk_{idx+1}")
                })
            
            # 确保 Cognee 已初始化
            await self.initialize()
            
            # 构建知识图谱
            build_result = await self.build_section_knowledge_graph(
                sections=sections,
                group_id=group_id,
                provider=provider
            )
            
            build_time = time.time() - build_start_time
            total_time = time.time() - start_time
            
            logger.info(
                f"✅ Cognee 知识图谱创建完成: group_id={group_id}, "
                f"章节数={len(sections)}, 构建耗时={build_time:.2f}秒, "
                f"总耗时={total_time:.2f}秒"
            )
            
            return {
                "exists": False,
                "created": True,
                "group_id": group_id,
                "section_count": len(sections),
                "check_time": build_start_time - start_time,
                "build_time": build_time,
                "total_time": total_time,
                "build_result": build_result
            }
            
        except Exception as e:
            build_time = time.time() - build_start_time
            logger.error(
                f"❌ Cognee 知识图谱创建失败: group_id={group_id}, "
                f"错误={e}, 耗时={build_time:.2f}秒",
                exc_info=True
            )
            return {
                "exists": False,
                "created": False,
                "error": str(e),
                "group_id": group_id,
                "build_time": build_time
            }
        finally:
            db.close()
    
    async def search_sections(
        self,
        query: str,
        group_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索章节内容
        
        Args:
            query: 查询文本
            group_id: 文档组 ID（可选，用于过滤）
            top_k: 返回数量
            
        Returns:
            搜索结果列表
        """
        await self.initialize()
        
        try:
            # 如果指定了 group_id，搜索对应的 dataset
            datasets = None
            if group_id:
                datasets = f"knowledge_base_{group_id}"
            
            # 使用 Cognee 搜索
            results = await self.cognee.search(
                query_text=query,
                datasets=datasets,
                top_k=top_k
            )
            
            # 转换结果格式
            formatted_results = []
            for result in results:
                if hasattr(result, 'content'):
                    formatted_results.append({
                        "content": result.content,
                        "metadata": getattr(result, 'metadata', {}),
                        "score": getattr(result, 'score', 0.0)
                    })
                elif isinstance(result, dict):
                    formatted_results.append(result)
                else:
                    formatted_results.append({"content": str(result)})
            
            return formatted_results[:top_k]
            
        except Exception as e:
            logger.error(f"Cognee 搜索失败: {e}", exc_info=True)
            return []

