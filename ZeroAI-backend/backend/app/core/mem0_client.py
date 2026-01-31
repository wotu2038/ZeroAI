"""
Mem0 客户端配置

用于对话记忆管理的持久化记忆层
"""
import logging
from typing import Optional, Dict
from mem0 import Memory
from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局 Mem0 实例字典（支持多个 provider）
_mem0_instances: Dict[str, Memory] = {}


def get_mem0_client(provider: str = "deepseek") -> Memory:
    """
    获取 Mem0 客户端实例（支持多个 provider）
    
    Args:
        provider: LLM提供商（deepseek/qwen/kimi），默认 deepseek
    
    Returns:
        Memory: Mem0 客户端实例
    """
    global _mem0_instances
    
    # 验证 provider
    if provider not in ["deepseek", "qwen", "kimi"]:
        raise ValueError(f"不支持的 provider: {provider}，仅支持 deepseek/qwen/kimi")
    
    # 如果已存在该 provider 的实例，直接返回
    if provider in _mem0_instances:
        return _mem0_instances[provider]
    
    try:
        import os
        
        # 步骤1：根据 provider 选择配置
        if provider == "deepseek":
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API key 未配置")
            api_key = settings.DEEPSEEK_API_KEY
            base_url = settings.DEEPSEEK_API_BASE.rstrip('/')
            model = settings.DEEPSEEK_MODEL
        elif provider == "qwen":
            if not settings.QWEN_API_KEY:
                raise ValueError("Qwen API key 未配置")
            api_key = settings.QWEN_API_KEY
            base_url = settings.QWEN_API_BASE.rstrip('/')
            # Qwen 需要 compatible-mode/v1
            if "/compatible-mode/v1" not in base_url:
                if "/compatible-mode" not in base_url:
                    base_url = f"{base_url}/compatible-mode/v1"
                else:
                    if not base_url.endswith("/v1"):
                        base_url = f"{base_url}/v1"
            model = settings.QWEN_MODEL
        elif provider == "kimi":
            if not settings.KIMI_API_KEY:
                raise ValueError("Kimi API key 未配置")
            api_key = settings.KIMI_API_KEY
            base_url = settings.KIMI_API_BASE.rstrip('/')
            model = settings.KIMI_MODEL
        else:
            raise ValueError(f"不支持的 provider: {provider}")
        
        # 确保 base_url 包含 /v1（OpenAI 兼容接口需要）
        # 注意：Qwen 的 base_url 已经在上面处理过了，这里只处理 DeepSeek 和 Kimi
        if provider != "qwen":
            if not base_url.endswith("/v1"):
                if "/v1" not in base_url:
                    base_url = f"{base_url}/v1"
        
        # 设置环境变量，让 Mem0 的 OpenAI provider 使用配置的 LLM
        # Mem0 的 OpenAI provider 会自动从环境变量读取 OPENAI_API_KEY 和 OPENAI_BASE_URL
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = base_url
        
        # 步骤2：配置向量存储（使用远程 Milvus）
        # bge-large-zh-v1.5 的维度是 1024
        # 根据 Mem0 源码和 MilvusClient 文档：
        # - url 参数：完整的 URI，可以在 URI 中包含认证信息（格式：http://username:password@host:port）
        # - token 参数：用于 Zilliz Cloud 的 API key，对于本地 Milvus 使用用户名密码时，token 可以为空字符串
        milvus_url = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        # 如果启用了认证，在 URL 中包含用户名和密码
        if settings.MILVUS_USERNAME and settings.MILVUS_PASSWORD:
            milvus_url = f"http://{settings.MILVUS_USERNAME}:{settings.MILVUS_PASSWORD}@{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        
        vector_store_config = {
            "collection_name": "mem0_memories",  # Mem0 记忆集合名称
            "embedding_model_dims": 1024,  # bge-large-zh-v1.5 的维度
            "url": milvus_url,  # 远程 Milvus URL（包含认证信息）
            "token": "",  # 对于使用用户名密码的 Milvus，token 为空字符串
        }
        
        # 步骤3：配置 Mem0
        # LLM: 使用配置的 LLM（DeepSeek/Qwen/Kimi，通过 OpenAI 兼容接口）
        # Embedder: 使用远程 Ollama（独立的配置）
        # Vector Store: 使用远程 Milvus
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": model,
                    # base_url 和 api_key 通过环境变量 OPENAI_BASE_URL 和 OPENAI_API_KEY 传递
                }
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": settings.OLLAMA_EMBEDDING_MODEL,
                    "ollama_base_url": settings.OLLAMA_BASE_URL,
                }
            },
            "vector_store": {
                "provider": "milvus",
                "config": vector_store_config,
            },
        }
        
        # 步骤4：使用 from_config 方法创建 Memory 实例
        mem0_instance = Memory.from_config(config)
        
        # 缓存实例
        _mem0_instances[provider] = mem0_instance
        
        logger.info(f"Mem0 客户端初始化成功 (provider={provider})")
        logger.info(f"  - LLM: {model} (via {base_url})")
        logger.info(f"  - Embedder: {settings.OLLAMA_EMBEDDING_MODEL} (via {settings.OLLAMA_BASE_URL})")
        
        return mem0_instance
        
    except Exception as e:
        logger.error(f"Mem0 客户端初始化失败: {e}")
        # 如果初始化失败，返回一个空实现以避免崩溃
        # 实际使用时需要处理这种情况
        raise


def clear_mem0_instances():
    """清除所有 Mem0 实例（用于测试）"""
    global _mem0_instances
    _mem0_instances = {}


def clear_mem0_instance(provider: Optional[str] = None):
    """清除指定 provider 的 Mem0 实例（用于测试）"""
    global _mem0_instances
    if provider:
        _mem0_instances.pop(provider, None)
    else:
        _mem0_instances = {}

