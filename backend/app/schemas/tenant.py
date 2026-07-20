"""
租户相关接口的请求/响应数据格式
"""

from pydantic import BaseModel


class TenantRegisterRequest(BaseModel):
    """注册接口的请求体：前端传 name、email、password"""
    name: str
    email: str
    password: str


class TenantLoginRequest(BaseModel):
    """登录接口的请求体：前端传 email、password"""
    email: str
    password: str


class TenantResponse(BaseModel):
    """返回给前端的租户信息，不含密码"""
    id: str
    name: str
    email: str
    api_key: str
    plan: str

    # 允许从 SQLAlchemy 对象直接转 Pydantic，不用手写 .dict()
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录成功后返回的 JWT token"""
    access_token: str
    token_type: str = "bearer"
