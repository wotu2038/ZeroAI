"""
Celery应用配置
"""
from celery import Celery
from celery.signals import worker_process_init
from app.core.config import settings

# 构建Redis连接URL（支持密码）
if settings.REDIS_PASSWORD:
    REDIS_URL = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
else:
    REDIS_URL = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

# 创建Celery应用
celery_app = Celery(
    "graphiti",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,  # 启用任务开始追踪
    task_time_limit=7200,     # 任务超时时间（2小时，大文档处理需要更长时间）
    task_soft_time_limit=6900,  # 软超时时间（1小时55分钟）
    worker_prefetch_multiplier=1,  # 每个worker一次只取一个任务
    worker_max_tasks_per_child=50,  # 防止内存泄漏
    result_expires=7200,  # 结果过期时间（2小时）
)

# 自动发现任务
celery_app.autodiscover_tasks(['app.tasks'])

# 显式导入任务模块以确保注册
try:
    from app.tasks import document_processing
    from app.tasks import requirement_generation
    from app.tasks import build_communities
    from app.tasks import generate_template
    from app.tasks import kb_document_processing
    from app.tasks import enhanced_document_processing  # 增强版文档处理任务
except ImportError as e:
    import logging
    logging.warning(f"Failed to import tasks: {e}")

# 预加载 Cognee 模块（在 worker 启动时）
# 这样可以避免每次任务执行时都要等待导入，解决导入阻塞问题
def _preload_cognee():
    """预加载 Cognee 模块，避免任务执行时的导入阻塞"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("开始预加载 Cognee 模块...")
        from app.services.cognee_service import get_cognee
        
        # 调用 get_cognee() 会触发 cognee 模块的导入
        # 这个过程可能需要一些时间（约10-15秒），但只需要执行一次
        cognee = get_cognee()
        logger.info(f"✅ Cognee 模块预加载成功，类型: {type(cognee)}")
        return True
    except Exception as e:
        # 预加载失败不影响 worker 启动，但会记录警告
        # 任务执行时会重新尝试加载
        logger.warning(f"⚠️ Cognee 模块预加载失败: {e}，任务执行时会重新尝试加载")
        logger.debug(f"Cognee 预加载失败详情: {type(e).__name__}: {str(e)}", exc_info=True)
        return False

# 使用 Celery 信号在每个 worker 进程启动时预加载 Cognee
# 这样可以确保每个 worker 进程都有预加载的 Cognee 模块
@worker_process_init.connect
def worker_process_init_handler(sender=None, **kwargs):
    """在每个 worker 进程启动时预加载 Cognee 模块并初始化配置"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Worker 进程启动，开始初始化配置...")
    
    # 初始化 Cognee Neo4j 配置（必须在导入 Cognee 之前设置）
    # 这是解决 Cognee 无法创建 Neo4j 节点的关键
    try:
        from app.utils.init_cognee_neo4j_config import init_cognee_neo4j_config
        success = init_cognee_neo4j_config()
        if success:
            logger.info("✅ Cognee Neo4j 配置初始化完成（Celery worker 进程启动时）")
        else:
            logger.warning("⚠️ Cognee Neo4j 配置初始化未完全成功")
    except Exception as e:
        logger.warning(f"Cognee Neo4j 配置初始化失败: {e}")
        import traceback
        logger.debug(f"Cognee Neo4j 配置初始化错误详情: {traceback.format_exc()}")
    
    # 预加载 Cognee 模块（在环境变量设置之后）
    logger.info("开始预加载 Cognee 模块...")
    _preload_cognee()
    
    # 初始化 Cognee LLM 配置（解决 @lru_cache + Pipeline 多进程配置传递问题）
    try:
        from app.utils.init_cognee_llm_config import init_cognee_llm_config_sync
        success = init_cognee_llm_config_sync()
        if success:
            logger.info("✅ Cognee LLM 配置初始化完成（Celery worker 进程启动时）")
        else:
            logger.warning("⚠️ Cognee LLM 配置初始化未完全成功，但环境变量已设置")
    except Exception as e:
        logger.warning(f"Cognee LLM 配置初始化失败: {e}")
        import traceback
        logger.debug(f"Cognee LLM 配置初始化错误详情: {traceback.format_exc()}")

