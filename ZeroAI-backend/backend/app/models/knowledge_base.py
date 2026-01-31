"""
知识库相关模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, ForeignKey, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.mysql_client import Base
import enum
from datetime import datetime


# 文档-知识库多对多关联表（放在此处避免循环导入）
document_knowledge_base_association = Table(
    'document_knowledge_base_association',
    Base.metadata,
    Column('document_id', Integer, ForeignKey('document_library.id'), primary_key=True),
    Column('knowledge_base_id', Integer, ForeignKey('knowledge_bases.id'), primary_key=True),
    Column('added_at', DateTime, default=datetime.now)
)


class KnowledgeBaseVisibility(enum.Enum):
    """知识库可见性枚举"""
    PRIVATE = "private"  # 个人知识库
    SHARED = "shared"     # 共享知识库


class MemberRole(enum.Enum):
    """成员角色枚举"""
    OWNER = "owner"      # 创建者
    ADMIN = "admin"      # 管理员
    EDITOR = "editor"    # 编辑者
    VIEWER = "viewer"    # 查看者


class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = "knowledge_bases"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(Text, nullable=True, comment="知识库描述")
    cover_icon = Column(String(50), default="folder", comment="封面图标")
    cover_image = Column(String(255), nullable=True, comment="封面图片URL（可选）")
    creator_name = Column(String(100), nullable=True, comment="创建者名称")
    category = Column(String(50), nullable=True, comment="分类（科技、教育、职场等）")
    visibility = Column(Enum(KnowledgeBaseVisibility), default=KnowledgeBaseVisibility.PRIVATE, nullable=False, comment="可见性")
    default_template_id = Column(Integer, nullable=True, comment="关联的默认模板ID")
    member_count = Column(Integer, default=1, nullable=False, comment="成员数量")
    document_count = Column(Integer, default=0, nullable=False, comment="文档数量")
    last_updated_at = Column(DateTime, nullable=True, comment="最后更新时间")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
    
    # 关系
    members = relationship("KnowledgeBaseMember", back_populates="knowledge_base", cascade="all, delete-orphan")
    
    # 文档库关联（多对多）
    library_documents = relationship(
        "DocumentLibrary",
        secondary="document_knowledge_base_association",
        back_populates="knowledge_bases"
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "cover_icon": self.cover_icon,
            "cover_image": self.cover_image,
            "creator_name": self.creator_name,
            "category": self.category,
            "visibility": self.visibility.value if self.visibility else None,
            "default_template_id": self.default_template_id,
            "member_count": self.member_count,
            "document_count": self.document_count,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class KnowledgeBaseMember(Base):
    """知识库成员表"""
    __tablename__ = "knowledge_base_members"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, comment="知识库ID")
    member_name = Column(String(100), nullable=False, comment="成员名称")
    role = Column(Enum(MemberRole), default=MemberRole.VIEWER, nullable=False, comment="成员角色")
    joined_at = Column(DateTime, server_default=func.now(), nullable=False, comment="加入时间")
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="members")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "member_name": self.member_name,
            "role": self.role.value if self.role else None,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None
        }

