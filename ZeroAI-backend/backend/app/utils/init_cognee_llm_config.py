"""
Cognee LLM Config 初始化工具

解决 @lru_cache + Pipeline 多进程配置传递问题：
- 方案三：环境变量兜底（最稳定，子进程一定能拿到）
- 方案二：显式清空缓存 + 重新设置配置

在以下时机调用：
1. FastAPI 应用启动时（app/main.py startup_event）
2. Celery worker 进程启动时（celery_app.py worker_process_init_handler）
"""

import logging
import os
from app.core.config import settings

logger = logging.getLogger(__name__)


async def init_cognee_llm_config():
    """
    初始化 Cognee LLM 配置
    
    按照 GPT 建议的方案：
    1. 设置环境变量（方案三：环境变量兜底）
    2. 清空缓存并重新设置配置（方案二：显式清空缓存）
    3. 禁用 litellm 的 aiohttp 传输（解决 Server disconnected 问题）
    
    确保 get_llm_config() 第一次调用时就能拿到正确配置
    """
    try:
        if not hasattr(settings, 'LOCAL_LLM_API_KEY') or not settings.LOCAL_LLM_API_KEY:
            logger.warning("⚠️ LOCAL_LLM_API_KEY 未设置，跳过 Cognee LLM 配置初始化")
            return False
        
        # ========== 关键修复：禁用 litellm 的 aiohttp 传输，改用 httpx ==========
        # 问题：litellm 使用 aiohttp 时出现 "Server disconnected" 错误
        # 原因：LLM 服务对 aiohttp 的异步连接处理有问题
        # 解决：禁用 aiohttp，改用 httpx（更稳定）
        try:
            import litellm
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
        
        local_base_url = None
        litellm_model = None
        
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
            if litellm_model:
                llm_config_obj = LLMConfig(
                    provider="openai",
                    model=litellm_model,
                    api_key=settings.LOCAL_LLM_API_KEY
                )
                await save_llm_config(llm_config_obj)
                
                # 手动设置 llm_endpoint（save_llm_config 不会设置）
                fresh_config = get_llm_config()
                if local_base_url:
                    fresh_config.llm_endpoint = local_base_url
                fresh_config.llm_api_key = settings.LOCAL_LLM_API_KEY  # 确保设置
                fresh_config.llm_model = litellm_model  # 确保设置
                
                logger.info(f"✅ 配置已重新设置: llm_model={fresh_config.llm_model}, llm_endpoint={fresh_config.llm_endpoint}, llm_api_key={'已设置' if fresh_config.llm_api_key else '未设置'}")
                
                # 验证配置
                final_config = get_llm_config()
                if final_config.llm_api_key and final_config.llm_api_key != "*****":
                    logger.info(f"✅ 配置验证成功: llm_api_key 已设置, llm_model={final_config.llm_model}, llm_endpoint={final_config.llm_endpoint}")
                    return True
                else:
                    logger.warning(f"⚠️ 配置验证失败: llm_api_key={final_config.llm_api_key}, llm_endpoint={final_config.llm_endpoint}")
                    return False
            else:
                logger.warning("⚠️ litellm_model 未设置，跳过配置设置")
                return False
        except Exception as e:
            logger.warning(f"⚠️ 清空缓存或重新设置配置失败: {e}")
            logger.warning("⚠️ 将继续使用环境变量（方案三），这应该足够稳定")
            import traceback
            logger.debug(f"配置设置错误详情: {traceback.format_exc()}")
            # 即使配置设置失败，环境变量已设置，应该也能工作
            return True
        
    except Exception as e:
        logger.error(f"❌ Cognee LLM 配置初始化失败: {e}", exc_info=True)
        return False


def init_cognee_llm_config_sync():
    """
    同步版本的 Cognee LLM 配置初始化
    
    用于 Celery worker 进程启动时（不支持 async）
    """
    import asyncio
    try:
        # 尝试获取事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，创建任务
            return loop.create_task(init_cognee_llm_config())
        else:
            # 如果事件循环未运行，直接运行
            return loop.run_until_complete(init_cognee_llm_config())
    except RuntimeError:
        # 如果没有事件循环，创建新的
        return asyncio.run(init_cognee_llm_config())

