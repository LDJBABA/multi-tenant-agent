from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base
import uuid
from datetime import datetime

class ToolConfig(Base):
    __tablename__ = "tool_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(100), nullable=False)           # 工具名称
    description = Column(Text, nullable=False)            # 给 LLM 看的描述
    parameters = Column(JSONB, nullable=False, default={}) # 参数 schema
    endpoint = Column(String(500), nullable=False)        # 调用地址
    method = Column(String(10), default="POST")           # HTTP 方法
    auth_type = Column(String(50), default="none")        # bearer / api_key / none
    auth_config = Column(JSONB, default={})               # 认证配置
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
