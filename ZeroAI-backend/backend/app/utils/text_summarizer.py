"""
文本概括工具（用于方案C）
"""
import hashlib
import logging
from typing import Optional
from app.core.llm_client import llm_client, LLMProvider
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


async def summarize_text(
    text: str,
    target_length: int,
    context: str = "",
    use_cache: bool = True
) -> str:
    """
    使用本地大模型概括文本到目标长度（带缓存和降级策略）
    
    注意：此功能仅支持本地大模型，不支持云端LLM（如千问）
    
    Args:
        text: 原始文本
        target_length: 目标长度（字符数）
        context: 上下文信息（如查询内容，帮助LLM理解重点）
        use_cache: 是否使用缓存
    
    Returns:
        概括后的文本
    """
    # 如果文本已经足够短，直接返回
    if len(text) <= target_length:
        return text
    
    # 生成缓存key
    cache_key = f"summarize:{hashlib.md5(f'{text}:{target_length}'.encode()).hexdigest()}"
    
    # 检查缓存
    if use_cache:
        try:
            redis_client = get_redis_client()
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"使用缓存的概括结果: {cache_key[:20]}...")
                return cached
        except Exception as e:
            logger.warning(f"Redis缓存读取失败，继续执行概括: {e}")
    
    # 调用本地大模型概括（固定使用 "local" provider）
    try:
        prompt = f"""请将以下文本概括到{target_length}字符以内，保留最重要的信息。

{f'查询上下文: {context}' if context else ''}

原始文本：
{text}

要求：
1. 保留核心信息和关键细节
2. 概括后的长度不超过{target_length}字符
3. 保持语义完整性和准确性
4. 只返回概括后的文本，不要其他内容"""
        
        messages = [
            {"role": "system", "content": "你是一个文本概括专家，擅长在保留核心信息的前提下压缩文本。"},
            {"role": "user", "content": prompt}
        ]
        
        # 固定使用本地大模型
        summarized = await llm_client.chat(
            provider="local",  # 固定使用本地大模型
            messages=messages,
            temperature=0.3,
            use_thinking=False
        )
        
        # 确保不超过目标长度
        if len(summarized) > target_length:
            summarized = summarized[:target_length]
        
        # 缓存结果（24小时过期）
        if use_cache:
            try:
                redis_client = get_redis_client()
                redis_client.setex(cache_key, 86400, summarized)  # 24小时 = 86400秒
                logger.debug(f"概括结果已缓存: {cache_key[:20]}...")
            except Exception as e:
                logger.warning(f"Redis缓存写入失败: {e}")
        
        return summarized
    except Exception as e:
        logger.warning(f"本地大模型概括失败，使用截断: {e}")
        # 降级到简单截断
        return _truncate_text(text, target_length)


def _truncate_text(text: str, target_length: int) -> str:
    """
    截断文本到目标长度（在段落边界截断）
    """
    if len(text) <= target_length:
        return text
    
    truncated = text[:target_length]
    if '\n\n' in truncated:
        truncated = truncated.rsplit('\n\n', 1)[0]
    elif '\n' in truncated:
        truncated = truncated.rsplit('\n', 1)[0]
    return truncated + "..."

