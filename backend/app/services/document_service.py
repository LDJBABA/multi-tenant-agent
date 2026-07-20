"""
文档业务逻辑层

职责：文件保存、数据库记录、查询文档列表
"""

import os
import uuid
import hashlib
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.tenant import Tenant
from app.tasks.ingest_task import ingest_document

# 上传文件存放目录，按租户隔离
UPLOAD_DIR = Path("uploads")


async def upload_document(
    db: AsyncSession,
    tenant: Tenant,
    filename: str,
    file_size: int,
    file_content: bytes,
) -> Document:
    """
    上传文档
    1. 按租户创建目录
    2. 用 UUID 重命名文件（防冲突、防路径注入）
    3. 保存文件到本地
    4. 写入数据库记录
    """
    #先查重
    # 计算文件 hash
    file_hash = hashlib.sha256(file_content).hexdigest()
    # 检查该租户是否已有相同文件
    existing = await db.execute(
        select(Document).where(
            Document.tenant_id == tenant.id,
            Document.file_hash == file_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("已存在相同内容的文档")

    # 创建租户目录：uploads/{tenant_id}/
    tenant_dir = UPLOAD_DIR / tenant.id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    # UUID 重命名，保留原始扩展名
    ext = Path(filename).suffix
    saved_name = f"{uuid.uuid4()}{ext}"
    file_path = tenant_dir / saved_name

    # 写入文件
    file_path.write_bytes(file_content)

    # 写入数据库
    document = Document(
        tenant_id=tenant.id,
        filename=filename,
        file_path=str(file_path),
        file_size=file_size,
        status="pending",
        file_hash=file_hash,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # 上传成功后，自动触发解析 → 切分
    await ingest_document(db, document)

    return document


async def list_documents(db: AsyncSession, tenant: Tenant) -> list[Document]:
    """查询当前租户的所有文档"""
    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == tenant.id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())

import os
from sqlalchemy import delete as sql_delete
from app.models.document import Document, Chunk
from app.rag.vector_store import delete_vectors


async def delete_document(db: AsyncSession, tenant: Tenant, document_id: str) -> None:
    """
    删除文档（文件 + 向量 + 数据库记录）
    1. 查找文档，验证归属
    2. 删除 Qdrant 向量
    3. 删除本地文件
    4. 删除 Chunk 记录
    5. 删除 Document 记录
    """
    # 查找文档
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant.id,  # 只能删自己的
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise ValueError("文档不存在")

    # 删除 Qdrant 向量
    delete_vectors(document_id)

    # 删除本地文件
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    # 删除 Chunk 记录
    await db.execute(
        sql_delete(Chunk).where(Chunk.document_id == document_id)
    )

    # 删除 Document 记录
    await db.delete(document)
    await db.commit()

async def get_document_chunks(
    db: AsyncSession, tenant: Tenant, document_id: str
) -> list[Chunk]:
    """查询指定文档的所有 chunk"""
    # 先验证文档归属
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant.id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise ValueError("文档不存在")

    # 查询 chunk
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    return list(result.scalars().all())
