"""
数据库迁移脚本：添加文档库相关表

执行方式：
docker-compose -f docker-compose.backend.yml exec zero-ai-backend python /app/migrations/add_document_library_tables.py
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.mysql_client import engine, Base
from app.models.document_library import DocumentLibrary, DocumentFolder, document_knowledge_base_association

def run_migration():
    """执行迁移"""
    print("开始创建文档库相关表...")
    
    try:
        # 创建表
        Base.metadata.create_all(bind=engine, tables=[
            DocumentFolder.__table__,
            DocumentLibrary.__table__,
            document_knowledge_base_association
        ])
        
        print("✅ 文档库表创建成功:")
        print("   - document_folders")
        print("   - document_library")
        print("   - document_knowledge_base_association")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        raise


if __name__ == "__main__":
    run_migration()

