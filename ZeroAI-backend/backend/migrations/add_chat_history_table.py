"""
创建对话历史表的迁移脚本
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.mysql_client import engine, Base
from app.models.chat_history import ChatHistory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_chat_history_table():
    """创建对话历史表"""
    try:
        logger.info("开始创建 chat_histories 表...")
        ChatHistory.__table__.create(engine, checkfirst=True)
        logger.info("chat_histories 表创建成功")
    except Exception as e:
        logger.error(f"创建 chat_histories 表失败: {e}")
        raise


if __name__ == "__main__":
    create_chat_history_table()

