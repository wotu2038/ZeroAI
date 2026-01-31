"""
文档上传记录模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.mysql_client import Base
import enum


class DocumentStatus(enum.Enum):
    """文档状态枚举"""
    VALIDATED = "validated"      # 已验证（仅上传验证）
    PARSING = "parsing"          # 解析中
    PARSED = "parsed"            # 已解析
    CHUNKING = "chunking"        # 分块中
    CHUNKED = "chunked"          # 已分块
    COMPLETED = "completed"      # 已完成（所有步骤完成）
    ERROR = "error"              # 处理错误


class DocumentUpload(Base):
    """文档上传记录表"""
    __tablename__ = "document_uploads"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    file_path = Column(String(500), nullable=False, comment="文件保存路径")
    file_extension = Column(String(10), nullable=False, comment="文件扩展名")
    status = Column(Enum(DocumentStatus), default=DocumentStatus.VALIDATED, nullable=False, comment="文档状态")
    upload_time = Column(DateTime, server_default=func.now(), nullable=False, comment="上传时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
    error_message = Column(Text, nullable=True, comment="错误信息")
    document_id = Column(String(100), nullable=True, comment="文档ID（group_id，处理完成后生成）")
    parsed_content_path = Column(String(500), nullable=True, comment="parsed_content文件路径（相对路径）")
    summary_content_path = Column(String(500), nullable=True, comment="summary_content文件路径（相对路径）")
    structured_content_path = Column(String(500), nullable=True, comment="structured_content文件路径（相对路径）")
    chunks_path = Column(String(500), nullable=True, comment="chunks文件路径（相对路径）")
    # 知识库相关字段
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True, comment="关联的知识库ID")
    # 文档库关联字段
    library_document_id = Column(Integer, ForeignKey("document_library.id", ondelete="SET NULL"), nullable=True, comment="关联的文档库文档ID")
    template_id = Column(Integer, nullable=True, comment="使用的模板ID（LLM生成或手动选择）")
    chunk_strategy = Column(String(50), nullable=True, comment="分块策略：level_1, level_2, level_3, level_4, level_5, fixed_token, no_split")
    max_tokens_per_section = Column(Integer, nullable=True, comment="每个章节的最大token数")
    analysis_mode = Column(String(50), nullable=True, comment="模板生成方案：smart_segment, full_chunk")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_path": self.file_path,
            "file_extension": self.file_extension,
            "status": self.status.value if self.status else None,
            "upload_time": self.upload_time.isoformat() if self.upload_time else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "error_message": self.error_message,
            "document_id": self.document_id,
            "parsed_content_path": self.parsed_content_path,
            "summary_content_path": self.summary_content_path,
            "structured_content_path": self.structured_content_path,
            "chunks_path": self.chunks_path,
            "knowledge_base_id": self.knowledge_base_id,
            "template_id": self.template_id,
            "chunk_strategy": self.chunk_strategy,
            "max_tokens_per_section": self.max_tokens_per_section,
            "analysis_mode": self.analysis_mode,
            "library_document_id": self.library_document_id
        }

