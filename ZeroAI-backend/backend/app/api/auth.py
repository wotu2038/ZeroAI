"""
用户认证API（登录、注册）
"""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from app.core.mysql_client import get_db
from app.models.user import User
from app.core.security import verify_password, get_password_hash
from app.core.jwt_utils import create_access_token
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["用户认证"])


class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str
    email: Optional[EmailStr] = None
    password: str


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: Optional[str]
    role: Optional[str] = None
    is_active: bool
    created_at: str


@router.post("/register", response_model=TokenResponse)
async def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """用户注册"""
    try:
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == request.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在（如果提供了邮箱）
        if request.email:
            existing_email = db.query(User).filter(User.email == request.email).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被注册"
                )
        
        # 创建新用户
        user = User(
            username=request.username,
            email=request.email,
            password_hash=get_password_hash(request.password),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 生成Token（sub必须是字符串）
        access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
        
        logger.info(f"用户注册成功: username={request.username}, id={user.id}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user.to_dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户注册失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/login", response_model=TokenResponse)
async def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """用户登录"""
    try:
        # 查找用户
        user = db.query(User).filter(User.username == request.username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 验证密码
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 检查用户是否激活
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用"
            )
        
        # 生成Token（sub必须是字符串）
        access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
        
        logger.info(f"用户登录成功: username={request.username}, id={user.id}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user.to_dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return UserResponse(**current_user.to_dict())

