"""
对话相关接口的请求/响应数据格式
"""

from datetime import datetime
from pydantic import BaseModel


class AskRequest(BaseModel):
    """提问请求体"""
    question: str                  # 用户的问题
    session_id: str | None = None  # 会话 ID，为空则新建会话


class AskResponse(BaseModel):
    """提问响应体"""
    answer: str                    # AI 的回答
    session_id: str                # 会话 ID（新建或已有的）
    retrieved_chunks: list[str]    # 检索到的 chunk 内容（调试用）
    retrieved_scores: list[float] = []  # 新增：相似度分数


class SessionResponse(BaseModel):
    """会话信息"""
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    """消息信息"""
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """消息列表响应"""
    messages: list[MessageResponse]
    total: int
