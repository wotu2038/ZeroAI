"""
Redis客户端（用于缓存）
"""
import redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# 全局Redis客户端实例
_redis_client = None


def get_redis_client() -> redis.Redis:
    """获取Redis客户端实例"""
    global _redis_client
    if _redis_client is None:
        try:
            redis_kwargs = {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "db": settings.REDIS_DB,
                "decode_responses": True,  # 自动解码为字符串
                "socket_connect_timeout": 5,
                "socket_timeout": 5
            }
            # 如果设置了密码，添加到连接参数
            if settings.REDIS_PASSWORD:
                redis_kwargs["password"] = settings.REDIS_PASSWORD
            
            _redis_client = redis.Redis(**redis_kwargs)
            # 测试连接
            _redis_client.ping()
            logger.info(f"Redis客户端连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
        except Exception as e:
            logger.error(f"Redis客户端连接失败: {e}")
            raise
    return _redis_client


def clear_redis_client():
    """清除Redis客户端缓存（用于重新加载配置）"""
    global _redis_client
    _redis_client = None

