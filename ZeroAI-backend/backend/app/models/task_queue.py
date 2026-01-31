"""
任务队列模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, JSON, Index
from sqlalchemy.sql import func
from app.core.mysql_client import Base
import enum


class TaskStatus(enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 待处理
    RUNNING = "running"        # 运行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class TaskType(enum.Enum):
    """任务类型枚举"""
    PROCESS_DOCUMENT = "process_document"  # 处理文档（步骤5）
    GENERATE_REQUIREMENT_DOCUMENT = "generate_requirement_document"  # 生成需求文档
    BUILD_COMMUNITIES = "build_communities"  # 构建Community（步骤6）
    GENERATE_TEMPLATE = "generate_template"  # LLM生成模板


class TaskQueue(Base):
    """任务队列表"""
    __tablename__ = "task_queue"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    task_id = Column(String(100), unique=True, nullable=False, comment="Celery任务ID")
    upload_id = Column(Integer, nullable=False, comment="文档上传ID")
    # 使用String类型存储枚举值，避免MySQL ENUM类型的匹配问题
    # 在应用层通过枚举类进行验证和转换
    task_type = Column(String(50), nullable=False, comment="任务类型")
    status = Column(String(20), default=TaskStatus.PENDING.value, nullable=False, comment="任务状态")
    progress = Column(Integer, default=0, nullable=False, comment="进度（0-100）")
    current_step = Column(String(200), nullable=True, comment="当前步骤描述")
    total_steps = Column(Integer, default=0, nullable=False, comment="总步骤数")
    completed_steps = Column(Integer, default=0, nullable=False, comment="已完成步骤数")
    result = Column(JSON, nullable=True, comment="任务结果（成功时）")
    error_message = Column(Text, nullable=True, comment="错误信息（失败时）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    
    # 创建索引
    __table_args__ = (
        Index('idx_status', 'status'),
        Index('idx_upload_id', 'upload_id'),
        Index('idx_task_id', 'task_id'),
        Index('idx_created_at', 'created_at'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "upload_id": self.upload_id,
            "task_type": self.task_type,  # 现在是字符串
            "status": self.status,  # 现在是字符串
            "progress": self.progress,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "result": self.result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

