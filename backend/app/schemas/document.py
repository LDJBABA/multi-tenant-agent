"""
文档相关接口的请求/响应数据格式
"""

from pydantic import BaseModel
from datetime import datetime


class DocumentResponse(BaseModel):
    """上传成功后返回的文档信息"""
    id: str
    filename: str
    file_size: int
    status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: list[DocumentResponse]
    total: int

class ChunkResponse(BaseModel):
    """单个 chunk 信息"""
    id: str
    chunk_index: int
    content: str
    token_count: int

    model_config = {"from_attributes": True}


class ChunkListResponse(BaseModel):
    """chunk 列表响应"""
    chunks: list[ChunkResponse]
    total: int
