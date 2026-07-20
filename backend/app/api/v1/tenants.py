"""
租户相关 API 路由

接口清单：
  POST /api/v1/tenants/register  注册
  POST /api/v1/tenants/login     登录
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_tenant
from app.models.tenant import Tenant

from app.core.database import get_db
from app.schemas.tenant import (
    TenantRegisterRequest,
    TenantLoginRequest,
    TenantResponse,
    TokenResponse,
)
from app.services import tenant_service

# prefix: 所有接口的 URL 前缀
# tags: API 文档里的分组名称（打开 /docs 能看到）
router = APIRouter(prefix="/tenants", tags=["租户"])


@router.post("/register", response_model=TenantResponse)
async def register(data: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    注册新租户
    - 请求体：name, email, password
    - 返回：租户信息（含 api_key）
    - 错误：400 = 邮箱已注册
    """
    try:
        tenant = await tenant_service.register_tenant(db, data)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(data: TenantLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    租户登录
    - 请求体：email, password
    - 返回：JWT access_token
    - 错误：401 = 邮箱或密码错误 / 账号已禁用
    """
    try:
        token = await tenant_service.login_tenant(db, data.email, data.password)
        return {"access_token": token}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=TenantResponse)
async def get_me(current_tenant: Tenant = Depends(get_current_tenant)):
    """获取当前登录租户的信息，需要在请求头带 Bearer token"""
    return current_tenant