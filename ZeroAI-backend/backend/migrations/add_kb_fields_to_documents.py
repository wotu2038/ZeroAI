"""
数据库迁移脚本：为document_uploads表添加知识库相关字段
执行方式：docker-compose exec backend python /app/migrations/add_kb_fields_to_documents.py
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
        logger.info("开始执行数据库迁移：为document_uploads表添加知识库相关字段")
        
        # 检查字段是否已存在
        check_column_sql = """
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'document_uploads'
        AND column_name = 'knowledge_base_id'
        """
        result = db.execute(text(check_column_sql))
        if result.fetchone()[0] > 0:
            logger.info("knowledge_base_id字段已存在，跳过添加")
        else:
            # 添加knowledge_base_id字段
            add_kb_id_sql = """
            ALTER TABLE document_uploads 
            ADD COLUMN knowledge_base_id INT NULL COMMENT '关联的知识库ID',
            ADD INDEX idx_knowledge_base_id (knowledge_base_id),
            ADD FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
            """
            db.execute(text(add_kb_id_sql))
            db.commit()
            logger.info("✅ knowledge_base_id字段添加成功")
        
        # 检查template_id字段
        check_template_sql = """
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'document_uploads'
        AND column_name = 'template_id'
        """
        result = db.execute(text(check_template_sql))
        if result.fetchone()[0] > 0:
            logger.info("template_id字段已存在，跳过添加")
        else:
            # 添加template_id字段
            add_template_id_sql = """
            ALTER TABLE document_uploads 
            ADD COLUMN template_id INT NULL COMMENT '使用的模板ID（LLM生成或手动选择）'
            """
            db.execute(text(add_template_id_sql))
            db.commit()
            logger.info("✅ template_id字段添加成功")
        
        # 检查chunk_strategy字段
        check_strategy_sql = """
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'document_uploads'
        AND column_name = 'chunk_strategy'
        """
        result = db.execute(text(check_strategy_sql))
        if result.fetchone()[0] > 0:
            logger.info("chunk_strategy字段已存在，跳过添加")
        else:
            # 添加chunk_strategy字段
            add_strategy_sql = """
            ALTER TABLE document_uploads 
            ADD COLUMN chunk_strategy VARCHAR(50) NULL COMMENT '分块策略：level_1, level_2, level_3, level_4, level_5, fixed_token, no_split'
            """
            db.execute(text(add_strategy_sql))
            db.commit()
            logger.info("✅ chunk_strategy字段添加成功")
        
        # 检查max_tokens_per_section字段
        check_tokens_sql = """
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'document_uploads'
        AND column_name = 'max_tokens_per_section'
        """
        result = db.execute(text(check_tokens_sql))
        if result.fetchone()[0] > 0:
            logger.info("max_tokens_per_section字段已存在，跳过添加")
        else:
            # 添加max_tokens_per_section字段
            add_tokens_sql = """
            ALTER TABLE document_uploads 
            ADD COLUMN max_tokens_per_section INT NULL COMMENT '每个章节的最大token数'
            """
            db.execute(text(add_tokens_sql))
            db.commit()
            logger.info("✅ max_tokens_per_section字段添加成功")
        
        # 检查analysis_mode字段
        check_mode_sql = """
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'document_uploads'
        AND column_name = 'analysis_mode'
        """
        result = db.execute(text(check_mode_sql))
        if result.fetchone()[0] > 0:
            logger.info("analysis_mode字段已存在，跳过添加")
        else:
            # 添加analysis_mode字段
            add_mode_sql = """
            ALTER TABLE document_uploads 
            ADD COLUMN analysis_mode VARCHAR(50) NULL COMMENT '模板生成方案：smart_segment, full_chunk'
            """
            db.execute(text(add_mode_sql))
            db.commit()
            logger.info("✅ analysis_mode字段添加成功")
        
        logger.info("✅ 数据库迁移完成！")
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

