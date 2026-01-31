"""
用户模型
"""
import enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.sql import func
from app.core.mysql_client import Base


class UserRole(enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"      # 管理员
    MANAGE = "manage"    # 管理
    COMMON = "common"    # 普通用户


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    email = Column(String(100), nullable=True, comment="邮箱")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    role = Column(Enum(UserRole), default=UserRole.COMMON, nullable=False, comment="用户角色")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
    
    def to_dict(self, exclude_password=True):
        """转换为字典"""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value if self.role else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        if not exclude_password:
            data["password_hash"] = self.password_hash
        return data

