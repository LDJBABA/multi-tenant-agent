"""
租户业务逻辑层

调用链：API 路由 → 这里 → 数据库/安全工具
职责：处理注册、登录的核心流程
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.schemas.tenant import TenantRegisterRequest
from app.core.security import hash_password, verify_password, create_access_token


async def register_tenant(db: AsyncSession, data: TenantRegisterRequest) -> Tenant:
    """
    注册新租户
    1. 检查邮箱是否已注册
    2. 创建租户（密码自动加密）
    3. 提交数据库
    """
    # 查重：邮箱唯一
    existing = await db.execute(select(Tenant).where(Tenant.email == data.email))
    if existing.scalar_one_or_none():
        raise ValueError("邮箱已注册")

    # 创建租户对象，密码加密后存储
    tenant = Tenant(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)  # 刷新拿到数据库生成的默认值（如 id、api_key）
    return tenant


async def login_tenant(db: AsyncSession, email: str, password: str) -> str:
    """
    租户登录
    1. 根据邮箱查找租户
    2. 验证密码
    3. 生成 JWT token
    """
    result = await db.execute(select(Tenant).where(Tenant.email == email))
    tenant = result.scalar_one_or_none()

    # 验证：租户存在 + 密码正确
    if not tenant or not verify_password(password, tenant.hashed_password):
        raise ValueError("邮箱或密码错误")

    # 验证：账号是否启用
    if not tenant.is_active:
        raise ValueError("账号已禁用")

    # 签发 JWT，payload 里带租户 ID
    token = create_access_token({"sub": tenant.id, "tenant_id": tenant.id})
    return token
