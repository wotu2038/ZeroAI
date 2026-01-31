"""
实体和关系模板模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Index
from sqlalchemy.sql import func
from app.core.mysql_client import Base


class EntityEdgeTemplate(Base):
    """实体和关系模板表"""
    __tablename__ = "entity_edge_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    category = Column(String(50), default="custom", nullable=False, comment="模板分类")
    entity_types = Column(JSON, nullable=False, comment="实体类型定义")
    edge_types = Column(JSON, nullable=False, comment="关系类型定义")
    edge_type_map = Column(JSON, nullable=False, comment="关系类型映射")
    is_default = Column(Boolean, default=False, nullable=False, comment="是否默认模板")
    is_system = Column(Boolean, default=False, nullable=False, comment="是否系统模板")
    is_llm_generated = Column(Boolean, default=False, nullable=False, comment="是否LLM生成")
    source_document_id = Column(Integer, nullable=True, comment="来源文档ID（LLM生成时关联）")
    analysis_mode = Column(String(50), nullable=True, comment="分析模式：smart_segment/full_chunk")
    llm_provider = Column(String(50), nullable=True, comment="LLM提供商（生成时使用）")
    generated_at = Column(DateTime, nullable=True, comment="生成时间")
    usage_count = Column(Integer, default=0, nullable=False, comment="使用次数")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
    created_by = Column(String(100), nullable=True, comment="创建人")
    
    __table_args__ = (
        Index('idx_category', 'category'),
        Index('idx_name', 'name'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "entity_types": self.entity_types,
            "edge_types": self.edge_types,
            "edge_type_map": self.edge_type_map,
            "is_default": self.is_default,
            "is_system": self.is_system,
            "is_llm_generated": self.is_llm_generated,
            "source_document_id": self.source_document_id,
            "analysis_mode": self.analysis_mode,
            "llm_provider": self.llm_provider,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by
        }

