"""
创建缺失的索引
"""
import sys
sys.path.insert(0, '/app')

from app.core.mysql_client import SessionLocal
from app.core.config import settings
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SessionLocal()
try:
    # 从配置读取数据库名
    database_name = settings.MYSQL_DATABASE
    
    # 检查并创建索引
    indexes = [
        ('idx_is_llm_generated', 'CREATE INDEX idx_is_llm_generated ON entity_edge_templates(is_llm_generated)'),
        ('idx_source_document_id', 'CREATE INDEX idx_source_document_id ON entity_edge_templates(source_document_id)')
    ]
    
    for idx_name, create_sql in indexes:
        # 检查索引是否存在
        check_sql = text(f"""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.STATISTICS 
            WHERE TABLE_SCHEMA = '{database_name}' 
            AND TABLE_NAME = 'entity_edge_templates' 
            AND INDEX_NAME = :idx_name
        """)
        result = db.execute(check_sql, {'idx_name': idx_name})
        if result.fetchone()[0] == 0:
            try:
                db.execute(text(create_sql))
                db.commit()
                logger.info(f"✅ 索引 {idx_name} 创建成功")
            except Exception as e:
                logger.warning(f"⚠️  索引 {idx_name} 创建失败: {e}")
                db.rollback()
        else:
            logger.info(f"✅ 索引 {idx_name} 已存在")
finally:
    db.close()

