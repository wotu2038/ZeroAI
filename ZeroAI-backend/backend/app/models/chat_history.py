"""
对话历史数据模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.mysql_client import Base
import enum


class ChatMode(enum.Enum):
    """对话模式枚举"""
    CONVERSATION = "conversation"  # 对话模式
    AGENT = "agent"  # Agent模式


class ChatHistory(Base):
    """对话历史表"""
    __tablename__ = "chat_histories"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    
    # 用户信息
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    
    # 知识库信息（可选，如果是知识库对话）
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True, comment="知识库ID")
    
    # 对话模式
    chat_mode = Column(SQLEnum(ChatMode), default=ChatMode.CONVERSATION, nullable=False, comment="对话模式")
    
    # 检索范围（用于多文档模式）
    group_ids = Column(JSON, nullable=True, comment="文档 group_id 列表（JSON数组）")
    all_documents = Column(String(10), default="false", nullable=False, comment="是否检索全部文档")
    
    # 检索配置
    retrieval_scheme = Column(String(50), default="default", nullable=False, comment="检索方案：default, enhanced, smart, fast")
    provider = Column(String(50), default="local", nullable=False, comment="LLM提供商：local, qianwen")
    use_thinking = Column(String(10), default="false", nullable=False, comment="是否启用Thinking模式")
    
    # 对话内容
    user_message = Column(Text, nullable=False, comment="用户消息")
    assistant_message = Column(Text, nullable=False, comment="助手回复")
    
    # 检索结果摘要（JSON格式，存储检索结果数量、耗时等）
    retrieval_summary = Column(JSON, nullable=True, comment="检索结果摘要：{count: 10, time: 1000, ...}")
    
    # 完整的检索结果（JSON格式，存储检索结果列表）
    retrieval_results = Column(JSON, nullable=True, comment="完整的检索结果列表（JSON数组）")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    
    # 关系
    user = relationship("User", backref="chat_histories")
    knowledge_base = relationship("KnowledgeBase", backref="chat_histories")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "knowledge_base_id": self.knowledge_base_id,
            "chat_mode": self.chat_mode.value if self.chat_mode else None,
            "group_ids": self.group_ids,
            "all_documents": self.all_documents == "true",
            "retrieval_scheme": self.retrieval_scheme,
            "provider": self.provider,
            "use_thinking": self.use_thinking == "true",
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "retrieval_summary": self.retrieval_summary,
            "retrieval_results": self.retrieval_results,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

