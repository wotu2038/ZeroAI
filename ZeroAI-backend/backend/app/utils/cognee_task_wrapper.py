"""
Cognee Task Wrapper

解决 Pipeline Task 执行时配置无法传递的问题：
在 Task 执行前，确保 LLM 配置正确设置
"""

import logging
import os
from functools import wraps
from app.core.config import settings

logger = logging.getLogger(__name__)


def ensure_llm_config_before_task(func):
    """
    装饰器：在 Task 执行前确保 LLM 配置正确设置
    
    使用方法：
    @ensure_llm_config_before_task
    async def my_task(...):
        ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 在 Task 执行前，确保环境变量和配置正确设置
        try:
            # ========== 关键修复：禁用 litellm 的 aiohttp 传输 ==========
            try:
                import litellm
                # 关键1：删除已缓存的 aiohttp handler
                if hasattr(litellm, 'base_llm_aiohttp_handler'):
                    litellm.base_llm_aiohttp_handler = None
                
                # 关键2：设置配置标志
                litellm.disable_aiohttp_transport = True
                litellm.use_aiohttp_transport = False
                logger.debug(f"Task Wrapper: 已禁用 aiohttp 传输")
            except Exception as e:
                logger.debug(f"无法禁用 aiohttp 传输: {e}")
            
            # 设置环境变量（方案三：环境变量兜底）
            if hasattr(settings, 'LOCAL_LLM_API_KEY') and settings.LOCAL_LLM_API_KEY:
                os.environ["LLM_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["OPENAI_API_KEY"] = settings.LOCAL_LLM_API_KEY
                os.environ["LLM_PROVIDER"] = "openai"
                
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
                    os.environ["LITELLM_MODEL"] = litellm_model
                
                # 清除缓存并重新设置配置（方案二：显式清空缓存）
                try:
                    from cognee.infrastructure.llm import get_llm_config
                    from cognee.modules.settings.save_llm_config import save_llm_config, LLMConfig
                    
                    get_llm_config.cache_clear()
                    
                    if 'litellm_model' in locals():
                        llm_config_obj = LLMConfig(
                            provider="openai",
                            model=litellm_model,
                            api_key=settings.LOCAL_LLM_API_KEY
                        )
                        await save_llm_config(llm_config_obj)
                        
                        fresh_config = get_llm_config()
                        if 'local_base_url' in locals():
                            fresh_config.llm_endpoint = local_base_url
                        fresh_config.llm_api_key = settings.LOCAL_LLM_API_KEY
                        if 'litellm_model' in locals():
                            fresh_config.llm_model = litellm_model
                        
                        logger.debug(f"✅ Task 执行前配置已设置: llm_model={fresh_config.llm_model}, llm_endpoint={fresh_config.llm_endpoint}")
                except Exception as e:
                    logger.warning(f"⚠️ Task 执行前配置设置失败: {e}")
                    # 继续执行，依赖环境变量
        except Exception as e:
            logger.warning(f"⚠️ Task 执行前环境变量设置失败: {e}")
        
        # 执行原始函数
        return await func(*args, **kwargs)
    
    return wrapper


def wrap_add_rule_associations():
    """
    包装 add_rule_associations 函数，确保在执行前配置正确
    
    返回包装后的函数
    """
    # 使用我们的 patched 版本，而不是原始版本
    from app.utils.patch_add_rule_associations import patched_add_rule_associations
    
    @ensure_llm_config_before_task
    async def wrapped_add_rule_associations(*args, **kwargs):
        """包装后的 add_rule_associations，确保配置正确"""
        return await patched_add_rule_associations(*args, **kwargs)
    
    return wrapped_add_rule_associations

