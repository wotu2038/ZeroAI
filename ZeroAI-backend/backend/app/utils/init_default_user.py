"""
初始化默认管理员用户
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.mysql_client import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_default_user():
    """初始化默认管理员用户
    
    配置项（必须在 .env 文件中设置）：
    - DEFAULT_ADMIN_USERNAME: 默认管理员用户名
    - DEFAULT_ADMIN_PASSWORD: 默认管理员密码
    - DEFAULT_ADMIN_EMAIL: 默认管理员邮箱
    
    如果未配置这些环境变量，将跳过管理员用户创建。
    """
    # 从 settings 读取配置（从 .env 读取）
    default_username = settings.DEFAULT_ADMIN_USERNAME
    default_password = settings.DEFAULT_ADMIN_PASSWORD
    default_email = settings.DEFAULT_ADMIN_EMAIL
    
    # 如果未配置管理员信息，跳过创建
    if not default_username or not default_password:
        logger.info("未配置 DEFAULT_ADMIN_USERNAME/PASSWORD，跳过默认管理员创建")
        logger.info("如需创建默认管理员，请在 .env 中配置 DEFAULT_ADMIN_* 环境变量")
        return
    
    db = SessionLocal()
    try:
        # 检查是否已存在该用户
        existing_user = db.query(User).filter(User.username == default_username).first()
        if existing_user:
            logger.info(f"默认管理员用户 '{default_username}' 已存在，跳过创建")
            return
        
        # 创建默认管理员用户
        admin_user = User(
            username=default_username,
            email=default_email or f"{default_username}@example.com",
            password_hash=get_password_hash(default_password),
            role=UserRole.ADMIN,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        logger.info(f"✅ 默认管理员用户创建成功: username={default_username}")
        logger.info("⚠️  请尽快修改默认密码！")
        
    except Exception as e:
        logger.error(f"❌ 创建默认管理员用户失败: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_default_user()

