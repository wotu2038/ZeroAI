"""
清理历史数据脚本

删除所有 DocumentUpload 和 TaskQueue 记录，以及相关文件

执行方式：
python -m app.migrations.cleanup_historical_data
"""
import os
import shutil
from sqlalchemy import text
from app.core.mysql_client import engine, SessionLocal
from app.models.document_upload import DocumentUpload
from app.models.task_queue import TaskQueue

def cleanup_historical_data():
    """清理历史数据"""
    db = SessionLocal()
    
    try:
        print("开始清理历史数据...")
        
        # 1. 收集所有 DocumentUpload 的文件路径
        uploads = db.query(DocumentUpload).all()
        file_paths = []
        parsed_content_dirs = []
        
        for upload in uploads:
            # 收集文件路径
            if upload.file_path:
                file_paths.append(upload.file_path)
            
            # 收集解析内容目录
            if upload.parsed_content_path:
                parsed_dir = os.path.dirname(upload.parsed_content_path)
                if parsed_dir and parsed_dir not in parsed_content_dirs:
                    parsed_content_dirs.append(parsed_dir)
        
        print(f"找到 {len(uploads)} 个 DocumentUpload 记录")
        print(f"找到 {len(file_paths)} 个文件路径")
        print(f"找到 {len(parsed_content_dirs)} 个解析内容目录")
        
        # 2. 删除文件
        deleted_files = 0
        deleted_dirs = 0
        
        for file_path in file_paths:
            if file_path:
                abs_path = file_path if os.path.isabs(file_path) else os.path.join("/app", file_path)
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                        deleted_files += 1
                        print(f"  删除文件: {file_path}")
                    except Exception as e:
                        print(f"  删除文件失败: {file_path}, 错误: {e}")
        
        # 3. 删除解析内容目录
        for parsed_dir in parsed_content_dirs:
            if parsed_dir:
                abs_dir = parsed_dir if os.path.isabs(parsed_dir) else os.path.join("/app", parsed_dir)
                if os.path.exists(abs_dir):
                    try:
                        shutil.rmtree(abs_dir)
                        deleted_dirs += 1
                        print(f"  删除目录: {parsed_dir}")
                    except Exception as e:
                        print(f"  删除目录失败: {parsed_dir}, 错误: {e}")
        
        # 4. 删除数据库记录
        with engine.connect() as connection:
            # 删除 TaskQueue 记录（如果表存在）
            try:
                result = connection.execute(text("DELETE FROM task_queue"))
                deleted_tasks = result.rowcount
                print(f"删除 {deleted_tasks} 个 TaskQueue 记录")
            except Exception as e:
                print(f"删除 TaskQueue 记录失败（表可能不存在）: {e}")
                deleted_tasks = 0
            
            # 删除 DocumentUpload 记录
            result = connection.execute(text("DELETE FROM document_uploads"))
            deleted_uploads = result.rowcount
            print(f"删除 {deleted_uploads} 个 DocumentUpload 记录")
            
            connection.commit()
        
        print("\n清理完成！")
        print(f"  - 删除文件: {deleted_files} 个")
        print(f"  - 删除目录: {deleted_dirs} 个")
        print(f"  - 删除 TaskQueue 记录: {deleted_tasks} 个")
        print(f"  - 删除 DocumentUpload 记录: {deleted_uploads} 个")
        
    except Exception as e:
        print(f"清理失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_historical_data()

