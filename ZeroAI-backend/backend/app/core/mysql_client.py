"""
MySQL数据库连接客户端
"""
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# 构建MySQL连接URL
MYSQL_URL = f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}?charset=utf8mb4"

# 创建数据库引擎
engine = create_engine(
    MYSQL_URL,
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=3600,    # 连接回收时间（秒）
    echo=False            # 是否打印SQL语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

# 获取数据库会话
def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 初始化数据库表
def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    logger.info("MySQL数据库表初始化完成")

