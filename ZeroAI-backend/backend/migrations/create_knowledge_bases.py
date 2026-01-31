"""
数据库迁移脚本：创建知识库相关表
执行方式：docker-compose exec backend python /app/migrations/create_knowledge_bases.py
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
        logger.info("开始执行数据库迁移：创建知识库相关表")
        
        # 检查knowledge_bases表是否已存在
        check_table_sql = """
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'knowledge_bases'
        """
        result = db.execute(text(check_table_sql))
        if result.fetchone()[0] > 0:
            logger.info("knowledge_bases表已存在，跳过创建")
        else:
            # 创建knowledge_bases表
            create_kb_table_sql = """
            CREATE TABLE knowledge_bases (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL COMMENT '知识库名称',
                description TEXT COMMENT '知识库描述',
                cover_icon VARCHAR(50) DEFAULT 'folder' COMMENT '封面图标',
                cover_image VARCHAR(255) COMMENT '封面图片URL（可选）',
                creator_name VARCHAR(100) COMMENT '创建者名称',
                category VARCHAR(50) COMMENT '分类（科技、教育、职场等）',
                visibility ENUM('private', 'shared') DEFAULT 'private' COMMENT '可见性',
                default_template_id INT COMMENT '关联的默认模板ID',
                member_count INT DEFAULT 1 COMMENT '成员数量',
                document_count INT DEFAULT 0 COMMENT '文档数量',
                last_updated_at DATETIME COMMENT '最后更新时间',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_creator (creator_name),
                INDEX idx_visibility (visibility),
                INDEX idx_category (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库表'
            """
            db.execute(text(create_kb_table_sql))
            db.commit()
            logger.info("✅ knowledge_bases表创建成功")
        
        # 检查knowledge_base_members表是否已存在
        check_members_table_sql = """
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'knowledge_base_members'
        """
        result = db.execute(text(check_members_table_sql))
        if result.fetchone()[0] > 0:
            logger.info("knowledge_base_members表已存在，跳过创建")
        else:
            # 创建knowledge_base_members表
            create_members_table_sql = """
            CREATE TABLE knowledge_base_members (
                id INT PRIMARY KEY AUTO_INCREMENT,
                knowledge_base_id INT NOT NULL,
                member_name VARCHAR(100) NOT NULL COMMENT '成员名称',
                role ENUM('owner', 'admin', 'editor', 'viewer') DEFAULT 'viewer',
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_kb_member (knowledge_base_id, member_name),
                INDEX idx_member (member_name),
                FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库成员表'
            """
            db.execute(text(create_members_table_sql))
            db.commit()
            logger.info("✅ knowledge_base_members表创建成功")
        
        logger.info("✅ 数据库迁移完成！")
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

