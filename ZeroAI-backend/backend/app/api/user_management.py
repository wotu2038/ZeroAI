"""
用户管理API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.core.mysql_client import get_db
from app.core.auth import get_current_admin_user
from app.models.user import User, UserRole
from app.api.auth import UserResponse
from app.services.user_service import UserService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user-management", tags=["用户管理"])


class UserCreateRequest(BaseModel):
    """创建用户请求"""
    username: str
    password: str
    email: Optional[EmailStr] = None
    role: str = "common"
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """更新用户请求"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    new_password: str


@router.get("", response_model=dict)
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词（搜索用户名和邮箱）"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取用户列表（仅Admin）"""
    try:
        users, total = UserService.get_users(
            db=db,
            page=page,
            page_size=page_size,
            keyword=keyword
        )
        
        users_list = [UserResponse(**user.to_dict()) for user in users]
        
        return {
            "users": [u.dict() for u in users_list],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取用户详情（仅Admin）"""
    try:
        user = UserService.get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        return UserResponse(**user.to_dict()).dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("", response_model=dict)
async def create_user(
    request: UserCreateRequest = Body(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """创建用户（仅Admin）"""
    try:
        user = UserService.create_user(
            db=db,
            username=request.username,
            password=request.password,
            email=request.email,
            role=request.role,
            is_active=request.is_active
        )
        
        if not user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        return UserResponse(**user.to_dict()).dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.put("/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    request: UserUpdateRequest = Body(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """更新用户（仅Admin）"""
    try:
        user = UserService.update_user(
            db=db,
            user_id=user_id,
            username=request.username,
            email=request.email,
            role=request.role,
            is_active=request.is_active
        )
        
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        return UserResponse(**user.to_dict()).dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """删除用户（仅Admin）"""
    try:
        # 不能删除自己
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="不能删除自己的账户")
        
        success = UserService.delete_user(db, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    request: ResetPasswordRequest = Body(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """重置用户密码（仅Admin）"""
    try:
        new_password = request.new_password
        if not new_password:
            raise HTTPException(status_code=400, detail="新密码不能为空")
        
        # 验证密码长度（bcrypt限制72字节）
        if len(new_password.encode('utf-8')) > 72:
            raise HTTPException(status_code=400, detail="密码长度不能超过72字节")
        
        success = UserService.reset_password(db, user_id, new_password)
        if not success:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        return {"message": "密码重置成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置密码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")

