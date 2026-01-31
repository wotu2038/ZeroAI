"""
迁移脚本：在 document_uploads 表添加 library_document_id 字段

执行方式：
python -m app.migrations.add_library_document_id_to_document_upload
"""
from sqlalchemy import text
from app.core.mysql_client import engine

def upgrade():
    """添加 library_document_id 字段"""
    with engine.connect() as connection:
        # 检查字段是否已存在
        result = connection.execute(text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'document_uploads'
            AND COLUMN_NAME = 'library_document_id'
        """))
        count = result.fetchone()[0]
        
        if count == 0:
            # 添加字段
            connection.execute(text("""
                ALTER TABLE document_uploads
                ADD COLUMN library_document_id INT NULL
                COMMENT '关联的文档库文档ID'
                AFTER knowledge_base_id
            """))
            
            # 添加外键约束
            connection.execute(text("""
                ALTER TABLE document_uploads
                ADD CONSTRAINT fk_document_upload_library_document
                FOREIGN KEY (library_document_id)
                REFERENCES document_library(id)
                ON DELETE SET NULL
            """))
            
            connection.commit()
            print("✅ library_document_id 字段添加成功")
        else:
            print("ℹ️  library_document_id 字段已存在，跳过")

def downgrade():
    """删除 library_document_id 字段"""
    with engine.connect() as connection:
        # 检查字段是否存在
        result = connection.execute(text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'document_uploads'
            AND COLUMN_NAME = 'library_document_id'
        """))
        count = result.fetchone()[0]
        
        if count > 0:
            # 删除外键约束
            connection.execute(text("""
                ALTER TABLE document_uploads
                DROP FOREIGN KEY fk_document_upload_library_document
            """))
            
            # 删除字段
            connection.execute(text("""
                ALTER TABLE document_uploads
                DROP COLUMN library_document_id
            """))
            
            connection.commit()
            print("✅ library_document_id 字段删除成功")
        else:
            print("ℹ️  library_document_id 字段不存在，跳过")

if __name__ == "__main__":
    upgrade()

