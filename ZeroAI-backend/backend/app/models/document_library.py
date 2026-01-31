"""
文档库数据模型

支持：
- 文件夹管理
- 文档与多个知识库关联
- 文档状态管理
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.mysql_client import Base
# 注意：document_knowledge_base_association 在 knowledge_base.py 中定义
# 这里使用字符串引用避免循环导入


class FolderType(enum.Enum):
    """文件夹类型"""
    USER = "user"      # 用户自定义文件夹
    SYSTEM = "system"  # 系统文件夹


class DocumentLibraryStatus(enum.Enum):
    """文档库状态"""
    UNASSIGNED = "unassigned"    # 未分配到知识库
    ASSIGNED = "assigned"        # 已分配到知识库
    PROCESSING = "processing"    # 处理中
    FAILED = "failed"            # 处理失败


class DocumentFolder(Base):
    """
    文档文件夹
    
    支持层级结构的文件夹管理
    """
    __tablename__ = 'document_folders'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # 父文件夹（支持层级）
    parent_id = Column(Integer, ForeignKey('document_folders.id'), nullable=True)
    
    # 文件夹类型
    folder_type = Column(String(50), default=FolderType.USER.value)
    
    # 排序权重
    sort_order = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    parent = relationship("DocumentFolder", remote_side=[id], backref="children")
    documents = relationship("DocumentLibrary", back_populates="folder")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "folder_type": self.folder_type,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "document_count": len(self.documents) if self.documents else 0
        }


class DocumentLibrary(Base):
    """
    文档库
    
    存储所有上传的文档，支持：
    - 文件夹分类
    - 多知识库关联
    - 状态管理
    """
    __tablename__ = 'document_library'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 文件信息
    file_name = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)  # 原始文件名
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # 文件大小（字节）
    file_type = Column(String(50), nullable=True)  # 文件类型：docx, pdf, etc.
    file_hash = Column(String(64), nullable=True)  # 文件哈希（用于去重）
    
    # 文件夹
    folder_id = Column(Integer, ForeignKey('document_folders.id'), nullable=True)
    
    # 状态
    status = Column(String(50), default=DocumentLibraryStatus.UNASSIGNED.value)
    
    # 元数据
    title = Column(String(500), nullable=True)  # 文档标题
    author = Column(String(255), nullable=True)  # 作者
    description = Column(Text, nullable=True)  # 描述
    tags = Column(Text, nullable=True)  # 标签（JSON数组）
    
    # 处理信息
    parsed_at = Column(DateTime, nullable=True)  # 解析时间
    error_message = Column(Text, nullable=True)  # 错误信息
    
    # 上传者
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    folder = relationship("DocumentFolder", back_populates="documents")
    knowledge_bases = relationship(
        "KnowledgeBase",
        secondary="document_knowledge_base_association",
        back_populates="library_documents"
    )
    uploader = relationship("User", backref="uploaded_documents")
    
    def to_dict(self, include_knowledge_bases: bool = False):
        result = {
            "id": self.id,
            "file_name": self.file_name,
            "original_name": self.original_name,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "folder_id": self.folder_id,
            "folder_name": self.folder.name if self.folder else None,
            "status": self.status,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "tags": self.tags,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
            "error_message": self.error_message,
            "uploaded_by": self.uploaded_by,
            "uploader_name": self.uploader.username if self.uploader else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_knowledge_bases:
            result["knowledge_bases"] = [
                {"id": kb.id, "name": kb.name}
                for kb in self.knowledge_bases
            ] if self.knowledge_bases else []
        
        return result


# 在 KnowledgeBase 模型中添加反向关系（需要更新现有模型）
# 在 knowledge_base.py 中添加：
# library_documents = relationship(
#     "DocumentLibrary",
#     secondary=document_knowledge_base_association,
#     back_populates="knowledge_bases"
# )

