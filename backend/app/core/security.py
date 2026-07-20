"""
安全工具：密码加密、JWT 生成与验证

流程：
  注册：明文密码 → hash_password() → 存入数据库
  登录：明文密码 + 数据库密文 → verify_password() → 通过 → create_access_token()
  鉴权：请求带 JWT → decode_access_token() → 提取租户信息
"""

from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt 加密器，密码只存密文，不可逆
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # token 有效期 24 小时


def hash_password(password: str) -> str:
    """明文密码 → 加密密文，注册时调用"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配数据库中的密文，登录时调用"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """生成 JWT token，data 里放租户 ID 等需要携带的信息"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.app_secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解析 JWT token，成功返回 payload（含租户 ID），失败返回 None"""
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
