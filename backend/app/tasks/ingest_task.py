"""
文档入库任务

职责：解析文件 → 切分文本 → 存入 Chunk 表
上传文件后自动触发
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.models.document import Chunk
from app.rag.parsers import parse_file
from app.rag.chunkers import chunk_text
from app.integrations.llm_client import embed_texts
from app.rag.vector_store import upsert_vectors
from app.rag.parsers import parse_file, parse_docx_structured
from app.rag.chunkers import chunk_text, chunk_text_structured



async def ingest_document(db: AsyncSession, document: Document) -> None:
    """
    处理单个文档：解析文件 → 切分文本 → 存入 Chunk 表 → Embedding → 存入 Qdrant

    流程：
    1. 更新文档状态为 processing
    2. 解析文件为纯文本
    3. 切分文本为多个 chunk
    4. 存入 Chunk 表
    5. 更新文档状态为 ready，记录 chunk 数量
    6. 失败则标记为 failed
    """
    try:
        # 标记为处理中
        document.status = "processing"
        await db.commit()

        # 解析文件
        file_path = document.file_path

        # 根据文件类型选择切分方式
        if file_path.endswith(".docx"):
            # DOCX：结构化切分
            elements = parse_docx_structured(file_path)
            chunks_data = chunk_text_structured(elements, min_tokens = 300, overlap = 0)
        else:
            # 其他格式：旧版切分
            text = parse_file(file_path)
            chunks_data = chunk_text(text)

        # 切分文本
        # chunks_data = chunk_text(text)

        # Embedding + 存入 Qdrant
        contents = [c["content"] for c in chunks_data]
        vectors = await embed_texts(contents)

        #实际存入向量库的chunk数据
        stored_chunks = upsert_vectors(
            tenant_id=document.tenant_id,
            document_id=document.id,
            chunks=chunks_data,
            vectors=vectors,
        )

        # 存入 Chunk 表
        for chunk_data in stored_chunks:
            chunk = Chunk(
                document_id=document.id,
                tenant_id=document.tenant_id,
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                chunk_index=chunk_data["chunk_index"],
            )
            db.add(chunk)

        # 更新文档状态
        document.status = "ready"
        document.chunk_count = len(stored_chunks)
        await db.commit()

    except Exception as e:
        # 失败则标记为 failed
        document.status = "failed"
        await db.commit()
        raise e

