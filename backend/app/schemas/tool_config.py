"""
工具配置接口的请求/响应数据格式
"""

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
from uuid import UUID


class ToolConfigCreate(BaseModel):
    """创建工具配置请求"""
    name: str
    description: str
    parameters: dict = {}
    endpoint: str
    method: str = "POST"
    auth_type: str = "none"
    auth_config: dict = {}


class ToolConfigUpdate(BaseModel):
    """更新工具配置请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[dict] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[dict] = None
    is_active: Optional[bool] = None


class ToolConfigResponse(BaseModel):
    """工具配置响应"""
    id: str
    tenant_id: str
    name: str
    description: str
    parameters: dict
    endpoint: str
    method: str
    auth_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "tenant_id", mode="before")
    @classmethod
    def uuid_to_str(cls, v):
        return str(v) if isinstance(v, UUID) else v


class ToolConfigListResponse(BaseModel):
    """工具配置列表响应"""
    tools: list[ToolConfigResponse]
    total: int
