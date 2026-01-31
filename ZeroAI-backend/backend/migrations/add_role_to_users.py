"""
添加role字段到users表
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.mysql_client import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """执行迁移"""
    try:
        with engine.connect() as conn:
            # 检查role字段是否已存在
            check_query = text("""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'users'
                AND COLUMN_NAME = 'role'
            """)
            result = conn.execute(check_query).fetchone()
            
            if result and result[0] > 0:
                logger.info("role字段已存在，跳过迁移")
                return
            
            # 添加role字段
            alter_query = text("""
                ALTER TABLE users
                ADD COLUMN role ENUM('admin', 'manage', 'common') NOT NULL DEFAULT 'common' COMMENT '用户角色'
                AFTER password_hash
            """)
            conn.execute(alter_query)
            conn.commit()
            
            logger.info("成功添加role字段到users表")
            
            # 将第一个用户设置为admin（如果还没有admin用户）
            # 先检查是否有admin用户
            check_admin_query = text("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
            admin_count = conn.execute(check_admin_query).fetchone()[0]
            
            if admin_count == 0:
                # 获取第一个用户的ID
                first_user_query = text("SELECT id FROM users ORDER BY id LIMIT 1")
                first_user_result = conn.execute(first_user_query).fetchone()
                if first_user_result:
                    first_user_id = first_user_result[0]
                    update_query = text("UPDATE users SET role = 'admin' WHERE id = :user_id")
                    conn.execute(update_query, {"user_id": first_user_id})
                    conn.commit()
                    logger.info(f"已将第一个用户（ID: {first_user_id}）设置为admin角色")
            else:
                logger.info("已存在admin用户，跳过设置")
            
    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    migrate()

