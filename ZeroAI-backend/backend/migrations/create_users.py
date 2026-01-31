"""
数据库迁移脚本：创建用户表
执行方式：docker-compose exec backend python /app/migrations/create_users.py
"""
import sys
import os
sys.path.insert(0, '/app')

from app.core.mysql_client import engine, SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """执行迁移"""
    db = SessionLocal()
    try:
        logger.info("开始执行数据库迁移：创建用户表")
        
        # 检查users表是否已存在
        check_table_sql = """
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'users'
        """
        result = db.execute(text(check_table_sql))
        if result.fetchone()[0] > 0:
            logger.info("users表已存在，跳过创建")
        else:
            # 创建users表
            create_users_table_sql = """
            CREATE TABLE users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
                email VARCHAR(100) COMMENT '邮箱',
                password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
                is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_username (username),
                INDEX idx_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表'
            """
            db.execute(text(create_users_table_sql))
            db.commit()
            logger.info("✅ users表创建成功")
        
        logger.info("✅ 数据库迁移完成！")
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

