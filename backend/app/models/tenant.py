"""
租户模型
"""

import secrets
import uuid
from sqlalchemy import Column, String, Boolean
from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, comment="企业名称")
    email = Column(String(255), unique=True, nullable=False, index=True, comment="登录邮箱，唯一")
    hashed_password = Column(String(255), nullable=False, comment="bcrypt加密后的密码")
    api_key = Column(
        String(64), unique=True, nullable=False,
        default=lambda: secrets.token_hex(32),
        comment="服务端API对接密钥，注册时自动生成"
    )
    plan = Column(String(20), default="free", comment="套餐：free/pro，用于配额和限流")
    is_active = Column(Boolean, default=True, comment="是否启用，禁用后所有接口不可访问")
