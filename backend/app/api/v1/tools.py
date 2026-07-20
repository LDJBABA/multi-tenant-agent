"""
工具配置管理 API 路由

接口清单：
  POST   /api/v1/tools        创建工具配置
  GET    /api/v1/tools        查询当前租户的工具列表
  PUT    /api/v1/tools/{id}   更新工具配置
  DELETE /api/v1/tools/{id}   删除工具配置
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import Tenant
from app.models.tool_config import ToolConfig
from app.schemas.tool_config import (
    ToolConfigCreate,
    ToolConfigUpdate,
    ToolConfigResponse,
    ToolConfigListResponse,
)

router = APIRouter(prefix="/tools", tags=["工具配置"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ToolConfigResponse)
async def create_tool(
    req: ToolConfigCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """创建工具配置"""
    tool = ToolConfig(
        tenant_id=current_tenant.id,
        name=req.name,
        description=req.description,
        parameters=req.parameters,
        endpoint=req.endpoint,
        method=req.method,
        auth_type=req.auth_type,
        auth_config=req.auth_config,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("/", response_model=ToolConfigListResponse)
async def list_tools(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """查询当前租户的工具列表"""
    result = await db.execute(
        select(ToolConfig)
        .where(ToolConfig.tenant_id == current_tenant.id)
        .order_by(ToolConfig.created_at.desc())
    )
    tools = list(result.scalars().all())
    return {"tools": tools, "total": len(tools)}


@router.put("/{tool_id}", response_model=ToolConfigResponse)
async def update_tool(
    tool_id: str,
    req: ToolConfigUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """更新工具配置"""
    result = await db.execute(
        select(ToolConfig).where(
            ToolConfig.id == tool_id,
            ToolConfig.tenant_id == current_tenant.id,
        )
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tool, key, value)

    await db.commit()
    await db.refresh(tool)
    return tool


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """删除工具配置"""
    result = await db.execute(
        select(ToolConfig).where(
            ToolConfig.id == tool_id,
            ToolConfig.tenant_id == current_tenant.id,
        )
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    await db.delete(tool)
    await db.commit()
    return {"detail": "删除成功"}
