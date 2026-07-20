"""
对话会话 + 消息
"""

import uuid
from sqlalchemy import Column, String, Integer, ForeignKey
from app.models.base import Base, TimestampMixin


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True, comment="所属租户")
    # 终端用户标识，可以是访客ID、手机号等，由接入方传入
    user_id = Column(String(255), nullable=False, comment="终端用户标识")
    # 新增：缓存的对话摘要
    summary = Column(String, nullable=True, comment="对话历史摘要，用于长对话上下文管理")
    summary_count = Column(Integer, default=0, comment="摘要覆盖的消息条数，用于增量更新判断")



class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True, comment="所属会话")
    role = Column(String(20), nullable=False, comment="消息角色：user=用户, assistant=AI, system=系统")
    content = Column(String, nullable=False, comment="消息内容")
    token_count = Column(Integer, default=0, comment="该消息的token数，用于上下文长度控制")
