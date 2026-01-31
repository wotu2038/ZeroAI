"""
用户管理服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from app.models.user import User, UserRole
from app.core.security import get_password_hash, verify_password
import logging

logger = logging.getLogger(__name__)


class UserService:
    """用户管理服务类"""
    
    @staticmethod
    def get_users(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None
    ) -> tuple[List[User], int]:
        """
        获取用户列表
        
        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 搜索关键词（搜索用户名和邮箱）
        
        Returns:
            (用户列表, 总数)
        """
        query = db.query(User)
        
        # 关键词搜索
        if keyword:
            keyword_pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    User.username.like(keyword_pattern),
                    User.email.like(keyword_pattern)
                )
            )
        
        # 获取总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
        
        return users, total
    
    @staticmethod
    def get_user(db: Session, user_id: int) -> Optional[User]:
        """获取用户详情"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def create_user(
        db: Session,
        username: str,
        password: str,
        email: Optional[str] = None,
        role: str = "common",
        is_active: bool = True
    ) -> Optional[User]:
        """
        创建用户
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
            email: 邮箱
            role: 角色（admin/manage/common）
            is_active: 是否激活
        
        Returns:
            User: 创建的用户对象，如果用户名已存在返回None
        """
        # 检查用户名是否已存在
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return None
        
        # 转换角色
        user_role = UserRole.ADMIN if role == "admin" else (
            UserRole.MANAGE if role == "manage" else UserRole.COMMON
        )
        
        # 创建用户
        user = User(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=user_role,
            is_active=is_active
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"用户创建成功: username={username}, role={role}")
        return user
    
    @staticmethod
    def update_user(
        db: Session,
        user_id: int,
        username: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[User]:
        """
        更新用户
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            username: 用户名
            email: 邮箱
            role: 角色
            is_active: 是否激活
        
        Returns:
            User: 更新后的用户对象，如果用户不存在返回None
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # 如果更新用户名，检查是否已存在
        if username is not None and username != user.username:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                raise ValueError(f"用户名 '{username}' 已存在")
            user.username = username
        
        if email is not None:
            user.email = email
        
        if role is not None:
            user_role = UserRole.ADMIN if role == "admin" else (
                UserRole.MANAGE if role == "manage" else UserRole.COMMON
            )
            user.role = user_role
        
        if is_active is not None:
            user.is_active = is_active
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"用户更新成功: user_id={user_id}")
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """
        删除用户
        
        Args:
            db: 数据库会话
            user_id: 用户ID
        
        Returns:
            bool: 是否删除成功
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        db.delete(user)
        db.commit()
        
        logger.info(f"用户删除成功: user_id={user_id}")
        return True
    
    @staticmethod
    def reset_password(db: Session, user_id: int, new_password: str) -> bool:
        """
        重置用户密码
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            new_password: 新密码
        
        Returns:
            bool: 是否重置成功
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        user.password_hash = get_password_hash(new_password)
        db.commit()
        
        logger.info(f"用户密码重置成功: user_id={user_id}")
        return True

