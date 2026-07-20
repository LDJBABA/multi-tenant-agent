"""
文档相关 API 路由

接口清单：
  POST /api/v1/documents/upload       上传文档
  GET  /api/v1/documents/             查询文档列表
  POST /api/v1/documents/chunks/by-ids  批量查询 chunk 内容
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.document import ChunkListResponse, DocumentResponse, DocumentListResponse
from app.services import document_service

# 允许的文件类型
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
# 单文件大小上限：20MB
MAX_FILE_SIZE = 20 * 1024 * 1024

router = APIRouter(prefix="/documents", tags=["文档"])
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    上传文档
    - 支持格式：PDF / DOCX / MD / TXT
    - 大小限制：20MB
    - 需要登录（Bearer token）
    """
    # 校验文件类型
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式：{ext}，允许：{', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 读取文件内容
    content = await file.read()

    # 校验文件大小
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制，最大 {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # 调用 service 保存文件
    document = await document_service.upload_document(
        db=db,
        tenant=current_tenant,
        filename=file.filename,
        file_size=len(content),
        file_content=content,
    )
    return document


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    查询当前租户的文档列表
    - 需要登录
    - 只返回自己的文档
    """
    documents = await document_service.list_documents(db, current_tenant)
    return {"documents": documents, "total": len(documents)}

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    删除文档
    - 需要登录
    - 只能删除自己的文档
    """
    try:
        await document_service.delete_document(db, current_tenant, document_id)
        return {"detail": "删除成功"}
    except Exception as e:
        logger.error(f"删除文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除失败")

@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def get_document_chunks(
    document_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """获取文档的 chunk 列表"""
    try:
        chunks = await document_service.get_document_chunks(db, current_tenant, document_id)
        return {"chunks": chunks, "total": len(chunks)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class ChunkIdsRequest(BaseModel):
    chunk_ids: list[str]


@router.post("/chunks/by-ids")
async def get_chunks_by_ids(
    req: ChunkIdsRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """批量查询 chunk 内容（从 Qdrant）"""
    from app.rag.vector_store import client, COLLECTION_NAME

    if not req.chunk_ids:
        return {"chunks": {}}

    # Qdrant point ID 是 int 类型，需转换
    int_ids = []
    for cid in req.chunk_ids:
        try:
            int_ids.append(int(cid))
        except ValueError:
            continue

    if not int_ids:
        return {"chunks": {}}

    # 从 Qdrant 按 point id 查询
    try:
        points = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=int_ids,
            with_payload=True,
        )
    except Exception:
        return {"chunks": {}}

    result = {}
    for point in points:
        result[str(point.id)] = point.payload.get("content", "")

    return {"chunks": result}
