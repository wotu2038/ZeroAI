from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from app.core.config import settings
from openai import AsyncOpenAI
import logging

logger = logging.getLogger(__name__)

# 全局Graphiti实例字典，支持多个LLM提供商
_graphiti_instances = {}

def clear_graphiti_instances():
    """清除Graphiti实例缓存（用于重新加载配置）"""
    global _graphiti_instances
    _graphiti_instances = {}


def get_graphiti_instance(provider: str = "qianwen") -> Graphiti:
    """获取Graphiti实例（支持千问和本地大模型）"""
    # 每次获取时都重新创建，确保使用最新的配置
    # 不缓存实例，避免配置更新后仍使用旧配置
    # if provider in _graphiti_instances:
    #     return _graphiti_instances[provider]
    
    # 根据提供商选择配置
    if provider == "qianwen" or provider == "qwen":
        if not settings.QWEN_API_KEY:
            raise ValueError("千问 API key not configured")
        
        # 千问的OpenAI兼容接口端点
        # 注意：OpenAI 客户端会自动在 base_url 后添加 /chat/completions
        # 所以 base_url 应该是：https://dashscope.aliyuncs.com/compatible-mode/v1
        # 最终请求 URL：https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
        qwen_base_url = settings.QWEN_API_BASE.rstrip('/')
        if "/compatible-mode/v1" not in qwen_base_url:
            if "/compatible-mode" not in qwen_base_url:
                qwen_base_url = f"{qwen_base_url}/compatible-mode/v1"
            else:
                # 如果已经有 compatible-mode，确保有 /v1
                if not qwen_base_url.endswith("/v1"):
                    qwen_base_url = f"{qwen_base_url}/v1"
        
        logger.info(f"千问 API base_url: {qwen_base_url}, model: {settings.QWEN_MODEL}")
        
        # 创建异步 OpenAI 客户端，设置更长的超时时间（5分钟）
        openai_client = AsyncOpenAI(
            api_key=settings.QWEN_API_KEY,
            base_url=qwen_base_url,
            timeout=300.0  # 5分钟超时
        )
        
        llm_config = LLMConfig(
            api_key=settings.QWEN_API_KEY,
            model=settings.QWEN_MODEL,
            base_url=qwen_base_url
        )
        llm_client = OpenAIGenericClient(config=llm_config, client=openai_client)
    elif provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DeepSeek API key not configured")
        
        # DeepSeek 使用 OpenAI 兼容接口
        deepseek_base_url = settings.DEEPSEEK_API_BASE.rstrip('/')
        if not deepseek_base_url.endswith("/v1"):
            if "/v1" not in deepseek_base_url:
                deepseek_base_url = f"{deepseek_base_url}/v1"
        
        logger.info(f"DeepSeek API base_url: {deepseek_base_url}, model: {settings.DEEPSEEK_MODEL}")
        
        openai_client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=deepseek_base_url,
            timeout=float(settings.DEEPSEEK_TIMEOUT) * 10.0  # 转换为秒
        )
        
        llm_config = LLMConfig(
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.DEEPSEEK_MODEL,
            base_url=deepseek_base_url
        )
        llm_client = OpenAIGenericClient(config=llm_config, client=openai_client)
    elif provider == "kimi":
        if not settings.KIMI_API_KEY:
            raise ValueError("Kimi API key not configured")
        
        # Kimi 使用 OpenAI 兼容接口
        kimi_base_url = settings.KIMI_API_BASE.rstrip('/')
        if not kimi_base_url.endswith("/v1"):
            if "/v1" not in kimi_base_url:
                kimi_base_url = f"{kimi_base_url}/v1"
        
        logger.info(f"Kimi API base_url: {kimi_base_url}, model: {settings.KIMI_MODEL}")
        
        openai_client = AsyncOpenAI(
            api_key=settings.KIMI_API_KEY,
            base_url=kimi_base_url,
            timeout=float(settings.KIMI_TIMEOUT) * 10.0  # 转换为秒
        )
        
        llm_config = LLMConfig(
            api_key=settings.KIMI_API_KEY,
            model=settings.KIMI_MODEL,
            base_url=kimi_base_url
        )
        llm_client = OpenAIGenericClient(config=llm_config, client=openai_client)
    elif provider == "local":
        if not settings.LOCAL_LLM_API_BASE_URL:
            raise ValueError("本地大模型 API base URL 未配置")
        
        # 本地大模型使用OpenAI兼容接口
        local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
        # 确保 base_url 包含 /v1（如果使用 OpenAI 兼容接口）
        if not local_base_url.endswith("/v1"):
            # 检查是否已经有 /v1，如果没有则添加
            if "/v1" not in local_base_url:
                local_base_url = f"{local_base_url}/v1"
        
        logger.info(f"本地大模型 API base_url: {local_base_url}, model: {settings.LOCAL_LLM_MODEL}")
        
        # 创建异步 OpenAI 客户端，设置更长的超时时间（5分钟）
        openai_client = AsyncOpenAI(
            api_key=settings.LOCAL_LLM_API_KEY,
            base_url=local_base_url,
            timeout=300.0  # 5分钟超时
        )
        
        llm_config = LLMConfig(
            api_key=settings.LOCAL_LLM_API_KEY,
            model=settings.LOCAL_LLM_MODEL,
            base_url=local_base_url
        )
        llm_client = OpenAIGenericClient(config=llm_config, client=openai_client)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    
    # 配置Ollama Embedding
    # 注意：Ollama使用OpenAI兼容的API
    embedder_config = OpenAIEmbedderConfig(
        api_key="not-required",  # Ollama不需要真实key，但需要非空值
        embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=f"{settings.OLLAMA_BASE_URL}/v1"
    )
    embedder = OpenAIEmbedder(config=embedder_config)
    
    # 配置Cross-encoder (Reranker)
    # 使用与LLM相同的配置，并传入带超时配置的客户端
    cross_encoder_config = LLMConfig(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url
    )
    # 为 Reranker 创建带超时配置的客户端（避免使用默认的 60 秒超时）
    cross_encoder_client = AsyncOpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        timeout=300.0  # 5分钟超时
    )
    cross_encoder = OpenAIRerankerClient(config=cross_encoder_config, client=cross_encoder_client)
    
    # 初始化Graphiti
    graphiti = Graphiti(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder
    )
    
    # 构建索引和约束（Graphiti需要这些来支持检索）
    # 注意：build_indices_and_constraints 是同步方法，不需要 await
    try:
        graphiti.build_indices_and_constraints()
        logger.info(f"Graphiti indices and constraints built for provider: {provider}")
    except Exception as e:
        logger.warning(f"Failed to build indices (may already exist): {e}")
    
    # 暂时不缓存，确保每次使用最新配置
    # _graphiti_instances[provider] = graphiti
    logger.info(f"Graphiti instance initialized for provider: {provider}, model: {llm_config.model}")
    
    return graphiti


# 默认使用千问
def get_default_graphiti() -> Graphiti:
    """获取默认Graphiti实例（千问）"""
    return get_graphiti_instance("qianwen")

