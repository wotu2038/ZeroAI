"""
密码加密工具
"""
import bcrypt
from passlib.context import CryptContext

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt密码最大长度（字节）
BCRYPT_MAX_PASSWORD_LENGTH = 72


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
    
    Returns:
        bool: 密码是否正确
    
    Note:
        bcrypt限制密码长度不能超过72字节，需要按字节截断
    """
    # bcrypt限制密码长度不能超过72字节，与加密时保持一致，按字节截断
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_LENGTH:
        password_bytes = password_bytes[:BCRYPT_MAX_PASSWORD_LENGTH]
    
    # 直接使用bcrypt验证
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    
    Args:
        password: 明文密码
    
    Returns:
        str: 密码哈希
    
    Note:
        bcrypt限制密码长度不能超过72字节，需要按字节截断
    """
    # bcrypt限制密码长度不能超过72字节，需要按字节截断
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_LENGTH:
        password_bytes = password_bytes[:BCRYPT_MAX_PASSWORD_LENGTH]
    
    # 直接使用bcrypt，避免passlib的初始化问题
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

