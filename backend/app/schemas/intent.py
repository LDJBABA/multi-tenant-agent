from pydantic import BaseModel, Field
from enum import Enum

class IntentType(str, Enum):
    knowledge = "knowledge"
    chitchat = "chitchat"
    action = "action"
    redirect = "redirect"

class IntentResult(BaseModel):
    """意图识别结果"""
    intent: IntentType = Field(description="用户意图分类")
    rewritten: str = Field(description="改写后的查询句，用于检索")
    params: dict = Field(default={}, description="action 类型时的参数")
