"""
对话相关 API 路由

接口清单：
  POST /api/v1/conversations/ask                      提问
  GET  /api/v1/conversations/sessions                  会话列表
  GET  /api/v1/conversations/sessions/{session_id}     会话消息
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.conversation import (
    AskRequest,
    AskResponse,
    SessionListResponse,
    MessageListResponse,
)
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["对话"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    data: AskRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    提问接口
    - 需要登录（Bearer token）
    - 传 session_id 继续已有对话，不传则新建
    - 返回 AI 回答 + 检索到的 chunk
    """
    result = await conversation_service.ask(
        db=db,
        tenant=current_tenant,
        question=data.question,
        session_id=data.session_id,
    )
    return result


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """获取当前租户的会话列表"""
    sessions = await conversation_service.list_sessions(db, current_tenant.id)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}", response_model=MessageListResponse)
async def get_session_messages(
    session_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """获取指定会话的消息列表"""
    try:
        messages = await conversation_service.get_session_messages(
            db, session_id, current_tenant.id
        )
        return {"messages": messages, "total": len(messages)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
