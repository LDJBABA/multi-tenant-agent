"""
通用依赖注入

用法：在路由函数参数里加 current_tenant = Depends(get_current_tenant)
即可拿到当前登录的租户对象
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.tenant import Tenant
from sqlalchemy import select

# HTTPBearer：自动从请求头 Authorization: Bearer <token> 里提取 token
security = HTTPBearer()


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    从 JWT token 中提取租户信息
    1. 解析 token 拿到 tenant_id
    2. 查询数据库拿到租户对象
    3. 验证租户是否启用
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="无效的 token")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="token 中缺少租户信息")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=401, detail="租户不存在")

    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")

    return tenant
