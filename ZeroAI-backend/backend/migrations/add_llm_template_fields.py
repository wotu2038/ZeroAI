"""
数据库迁移脚本：为模板表添加LLM生成相关字段
执行方式：docker-compose -f docker-compose.backend.yml exec zero-ai-backend python /app/migrations/add_llm_template_fields.py
或者：docker-compose exec zero-ai-backend python /app/migrations/add_llm_template_fields.py
"""
import sys
import os
sys.path.insert(0, '/app')

from app.core.mysql_client import engine, SessionLocal
from app.core.config import settings
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """执行迁移"""
    db = SessionLocal()
    try:
        logger.info("开始执行数据库迁移：添加LLM模板生成相关字段")
        
        # 从配置读取数据库名
        database_name = settings.MYSQL_DATABASE
        
        # 检查字段是否已存在
        check_sql = f"""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = '{database_name}' 
        AND TABLE_NAME = 'entity_edge_templates' 
        AND COLUMN_NAME = 'is_llm_generated'
        """
        result = db.execute(text(check_sql))
        if result.fetchone():
            logger.info("字段已存在，跳过迁移")
            return
        
        # 添加字段
        alter_sqls = [
            "ALTER TABLE entity_edge_templates ADD COLUMN is_llm_generated BOOLEAN DEFAULT FALSE NOT NULL COMMENT '是否LLM生成' AFTER is_system",
            "ALTER TABLE entity_edge_templates ADD COLUMN source_document_id INT NULL COMMENT '来源文档ID（LLM生成时关联）' AFTER is_llm_generated",
            "ALTER TABLE entity_edge_templates ADD COLUMN analysis_mode VARCHAR(50) NULL COMMENT '分析模式：smart_segment/full_chunk' AFTER source_document_id",
            "ALTER TABLE entity_edge_templates ADD COLUMN llm_provider VARCHAR(50) NULL COMMENT 'LLM提供商（生成时使用）' AFTER analysis_mode",
            "ALTER TABLE entity_edge_templates ADD COLUMN generated_at DATETIME NULL COMMENT '生成时间' AFTER llm_provider",
            # MySQL不支持IF NOT EXISTS，先检查索引是否存在
            (f"CREATE INDEX idx_is_llm_generated ON entity_edge_templates(is_llm_generated)", 
             f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = '{database_name}' AND TABLE_NAME = 'entity_edge_templates' AND INDEX_NAME = 'idx_is_llm_generated'"),
            (f"CREATE INDEX idx_source_document_id ON entity_edge_templates(source_document_id)",
             f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = '{database_name}' AND TABLE_NAME = 'entity_edge_templates' AND INDEX_NAME = 'idx_source_document_id'")
        ]
        
        for item in alter_sqls:
            try:
                if isinstance(item, tuple):
                    # 带检查的索引创建
                    check_sql, create_sql = item
                    check_result = db.execute(text(check_sql))
                    if check_result.fetchone()[0] == 0:
                        db.execute(text(create_sql))
                        db.commit()
                        logger.info(f"执行成功: {create_sql[:50]}...")
                    else:
                        logger.info(f"索引已存在，跳过: {create_sql[:50]}...")
                else:
                    # 普通SQL
                    db.execute(text(item))
                    db.commit()
                    logger.info(f"执行成功: {item[:50]}...")
            except Exception as e:
                logger.warning(f"执行失败（可能已存在）: {item[:50] if isinstance(item, str) else item[0][:50]}... - {e}")
                db.rollback()
        
        logger.info("✅ 数据库迁移完成！")
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

