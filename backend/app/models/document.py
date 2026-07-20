"""
文档模型
"""
import uuid
from sqlalchemy import Column, String, Integer, ForeignKey
from app.models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True, comment="所属租户")
    filename = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="服务器存储路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    status = Column(
        String(20), default="pending",
        comment="处理状态：pending=等待处理, processing=解析中, ready=可用, failed=失败"
    )
    chunk_count = Column(Integer, default=0, comment="切分后的片段数")
    # 文件内容 hash（SHA256），用于文件级去重
    file_hash = Column(String(64), nullable=True, comment="文件内容SHA256，用于去重")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True, comment="所属文档")
    # 冗余tenant_id，向量检索时按租户过滤用，避免跨表JOIN
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True, comment="所属租户")
    content = Column(String, nullable=False, comment="切分后的原文内容")
    token_count = Column(Integer, nullable=False, comment="该片段的token数")
    chunk_index = Column(Integer, nullable=False, comment="在文档中的顺序，从0开始")
    vector_id = Column(String, nullable=True, comment="Qdrant中的向量ID，用于后续检索关联")
