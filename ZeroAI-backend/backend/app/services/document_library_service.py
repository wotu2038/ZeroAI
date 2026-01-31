"""
文档库服务

提供文档库的增删改查功能：
- 文件夹管理
- 文档上传与管理
- 知识库关联
- 搜索与筛选
"""
import os
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.document_library import (
    DocumentLibrary,
    DocumentFolder,
    DocumentLibraryStatus,
    FolderType
)
from app.models.knowledge_base import document_knowledge_base_association
from app.core.mysql_client import SessionLocal

logger = logging.getLogger(__name__)


class DocumentLibraryService:
    """文档库服务"""
    
    # ==================== 文件夹管理 ====================
    
    @staticmethod
    def create_folder(
        name: str,
        parent_id: int = None,
        description: str = None,
        db: Session = None
    ) -> DocumentFolder:
        """创建文件夹"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            folder = DocumentFolder(
                name=name,
                parent_id=parent_id,
                description=description,
                folder_type=FolderType.USER.value
            )
            
            db.add(folder)
            db.commit()
            db.refresh(folder)
            
            logger.info(f"创建文件夹成功: {folder.id} - {name}")
            return folder
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def get_folder_tree(db: Session = None) -> List[Dict]:
        """获取文件夹树结构"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # 获取所有文件夹
            folders = db.query(DocumentFolder).order_by(DocumentFolder.sort_order).all()
            
            # 构建树结构
            folder_dict = {f.id: f.to_dict() for f in folders}
            
            # 添加子文件夹
            for folder in folders:
                folder_data = folder_dict[folder.id]
                folder_data["children"] = []
                
                if folder.parent_id and folder.parent_id in folder_dict:
                    parent = folder_dict[folder.parent_id]
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(folder_data)
            
            # 返回根文件夹
            return [f for f in folder_dict.values() if f.get("parent_id") is None]
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def delete_folder(folder_id: int, db: Session = None) -> bool:
        """删除文件夹（如果为空）"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
            if not folder:
                return False
            
            # 检查是否有子文件夹或文档
            if folder.children or folder.documents:
                raise ValueError("文件夹不为空，无法删除")
            
            db.delete(folder)
            db.commit()
            return True
            
        finally:
            if close_db:
                db.close()
    
    # ==================== 文档管理 ====================
    
    @staticmethod
    def upload_document(
        file_name: str,
        original_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        uploaded_by: int = None,
        folder_id: int = None,
        db: Session = None
    ) -> DocumentLibrary:
        """
        上传文档到文档库
        
        Args:
            file_name: 保存的文件名
            original_name: 原始文件名
            file_path: 文件路径
            file_size: 文件大小
            file_type: 文件类型
            uploaded_by: 上传者ID
            folder_id: 目标文件夹ID
            
        Returns:
            DocumentLibrary 对象
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # 计算文件哈希（用于去重）
            file_hash = DocumentLibraryService._calculate_file_hash(file_path)
            
            # 检查是否已存在相同文件
            existing = db.query(DocumentLibrary).filter(
                DocumentLibrary.file_hash == file_hash
            ).first()
            
            if existing:
                logger.info(f"文件已存在: {existing.id} - {original_name}")
                return existing
            
            # 创建文档记录
            document = DocumentLibrary(
                file_name=file_name,
                original_name=original_name,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                file_hash=file_hash,
                folder_id=folder_id,
                uploaded_by=uploaded_by,
                status=DocumentLibraryStatus.UNASSIGNED.value
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            logger.info(f"上传文档成功: {document.id} - {original_name}")
            return document
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """计算文件 MD5 哈希"""
        try:
            abs_path = file_path if os.path.isabs(file_path) else os.path.join("/app", file_path)
            
            hash_md5 = hashlib.md5()
            with open(abs_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"计算文件哈希失败: {e}")
            return ""
    
    @staticmethod
    def get_documents(
        folder_id: int = None,
        status: str = None,
        knowledge_base_id: int = None,
        search: str = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = None
    ) -> Tuple[List[DocumentLibrary], int]:
        """
        获取文档列表
        
        Args:
            folder_id: 文件夹ID
            status: 状态筛选
            knowledge_base_id: 知识库ID
            search: 搜索关键词
            page: 页码
            page_size: 每页数量
            
        Returns:
            (文档列表, 总数)
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            query = db.query(DocumentLibrary)
            
            # 文件夹筛选
            if folder_id is not None:
                query = query.filter(DocumentLibrary.folder_id == folder_id)
            
            # 状态筛选
            if status:
                query = query.filter(DocumentLibrary.status == status)
            
            # 知识库筛选
            if knowledge_base_id:
                query = query.join(
                    document_knowledge_base_association
                ).filter(
                    document_knowledge_base_association.c.knowledge_base_id == knowledge_base_id
                )
            
            # 搜索
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        DocumentLibrary.file_name.ilike(search_pattern),
                        DocumentLibrary.original_name.ilike(search_pattern),
                        DocumentLibrary.title.ilike(search_pattern),
                        DocumentLibrary.description.ilike(search_pattern)
                    )
                )
            
            # 统计总数
            total = query.count()
            
            # 分页
            query = query.order_by(DocumentLibrary.created_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            documents = query.all()
            
            return documents, total
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def get_document(document_id: int, db: Session = None) -> Optional[DocumentLibrary]:
        """获取单个文档"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            return db.query(DocumentLibrary).filter(
                DocumentLibrary.id == document_id
            ).first()
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def update_document(
        document_id: int,
        title: str = None,
        description: str = None,
        folder_id: int = None,
        tags: str = None,
        db: Session = None
    ) -> Optional[DocumentLibrary]:
        """更新文档信息"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            document = db.query(DocumentLibrary).filter(
                DocumentLibrary.id == document_id
            ).first()
            
            if not document:
                return None
            
            if title is not None:
                document.title = title
            if description is not None:
                document.description = description
            if folder_id is not None:
                document.folder_id = folder_id
            if tags is not None:
                document.tags = tags
            
            db.commit()
            db.refresh(document)
            
            return document
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def delete_document(document_id: int, db: Session = None) -> bool:
        """删除文档"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            document = db.query(DocumentLibrary).filter(
                DocumentLibrary.id == document_id
            ).first()
            
            if not document:
                return False
            
            # 删除关联的文件
            if document.file_path:
                try:
                    abs_path = document.file_path if os.path.isabs(document.file_path) \
                        else os.path.join("/app", document.file_path)
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                except Exception as e:
                    logger.warning(f"删除文件失败: {e}")
            
            db.delete(document)
            db.commit()
            
            return True
            
        finally:
            if close_db:
                db.close()
    
    # ==================== 知识库关联 ====================
    
    @staticmethod
    def add_to_knowledge_base(
        document_id: int,
        knowledge_base_id: int,
        db: Session = None
    ) -> bool:
        """将文档添加到知识库"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # 检查文档是否存在
            document = db.query(DocumentLibrary).filter(
                DocumentLibrary.id == document_id
            ).first()
            
            if not document:
                return False
            
            # 检查是否已关联
            from app.models.knowledge_base import KnowledgeBase
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.id == knowledge_base_id
            ).first()
            
            if not kb:
                return False
            
            # 添加关联
            if kb not in document.knowledge_bases:
                document.knowledge_bases.append(kb)
                document.status = DocumentLibraryStatus.ASSIGNED.value
                db.commit()
            
            return True
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def remove_from_knowledge_base(
        document_id: int,
        knowledge_base_id: int,
        db: Session = None
    ) -> bool:
        """从知识库移除文档"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            document = db.query(DocumentLibrary).filter(
                DocumentLibrary.id == document_id
            ).first()
            
            if not document:
                return False
            
            from app.models.knowledge_base import KnowledgeBase
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.id == knowledge_base_id
            ).first()
            
            if kb and kb in document.knowledge_bases:
                document.knowledge_bases.remove(kb)
                
                # 如果没有关联的知识库了，更新状态
                if not document.knowledge_bases:
                    document.status = DocumentLibraryStatus.UNASSIGNED.value
                
                db.commit()
            
            return True
            
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def get_unassigned_documents(
        page: int = 1,
        page_size: int = 20,
        db: Session = None
    ) -> Tuple[List[DocumentLibrary], int]:
        """获取未分配的文档"""
        return DocumentLibraryService.get_documents(
            status=DocumentLibraryStatus.UNASSIGNED.value,
            page=page,
            page_size=page_size,
            db=db
        )
    
    # ==================== 统计 ====================
    
    @staticmethod
    def get_statistics(db: Session = None) -> Dict[str, Any]:
        """获取文档库统计信息"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            total_documents = db.query(DocumentLibrary).count()
            
            unassigned = db.query(DocumentLibrary).filter(
                DocumentLibrary.status == DocumentLibraryStatus.UNASSIGNED.value
            ).count()
            
            assigned = db.query(DocumentLibrary).filter(
                DocumentLibrary.status == DocumentLibraryStatus.ASSIGNED.value
            ).count()
            
            failed = db.query(DocumentLibrary).filter(
                DocumentLibrary.status == DocumentLibraryStatus.FAILED.value
            ).count()
            
            total_folders = db.query(DocumentFolder).count()
            
            # 按文件类型统计
            from sqlalchemy import func
            type_stats = db.query(
                DocumentLibrary.file_type,
                func.count(DocumentLibrary.id)
            ).group_by(DocumentLibrary.file_type).all()
            
            return {
                "total_documents": total_documents,
                "unassigned": unassigned,
                "assigned": assigned,
                "failed": failed,
                "total_folders": total_folders,
                "by_type": {t: c for t, c in type_stats if t}
            }
            
        finally:
            if close_db:
                db.close()

