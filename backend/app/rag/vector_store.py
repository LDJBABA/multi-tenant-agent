"""
向量存储

封装 Qdrant 操作：
- upsert_vectors：存入向量（入库时用）
- search_vectors：搜索向量（查询时用）
"""
import hashlib
from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
# Qdrant 客户端
client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

# Collection 名称
COLLECTION_NAME = "knowledge_chunks"

# 向量维度（百炼 text-embedding-v3 输出 1024 维）
VECTOR_SIZE = 1024

#最大语义相似度，如果超过这个就判断为内容相似，跳过
MAX_SIMILARITY = 0.90


def ensure_collection():
    """确保 Collection 存在，不存在则创建"""
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,  # 余弦相似度
            ),
        )


def upsert_vectors(
    tenant_id: str,
    document_id: str,
    chunks: list[dict],
    vectors: list[list[float]],
) -> list[dict]:
    """
    批量存入向量

    参数：
        tenant_id: 租户 ID（检索时过滤用）
        document_id: 文档 ID
        chunks: [{"content": "...", "chunk_index": 0}, ...]
        vectors: [[0.123, ...], [0.456, ...], ...]
    """
    ensure_collection()

    points = []
    stored_chunks = []
    for chunk, vector in zip(chunks, vectors):
        # 第 2 层：content hash 生成 Point ID，已存在则 skip
        point_id = make_int_point_id(tenant_id, chunk['content_hash'])

        existing = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
        )
        if existing:
            logger.info(f"Chunk [{chunk['content']}] 已存在，跳过.")
            continue  # 已存在，跳过

        # 第 3 层：Embedding 相似度预检
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter={
                "must": [{"key": "tenant_id", "match": {"value": tenant_id}}]
            },
            limit=1,
        )
        if search_result.points and search_result.points[0].score > 0.90:
            logger.info(f"Chunk 【{chunk['content']}】 存在语义相似度【{search_result.points[0].score}】极为相似的 chunk 【{search_result.points[0].payload['content']}】, 跳过.")
            continue  # 语义重复，跳过
        
        point = PointStruct(
            # 用文档ID+序号生成唯一 ID
            id=point_id,
            vector=vector,
            payload={
                "tenant_id": tenant_id,
                "document_id": document_id,
                "content": chunk["content"],
                "chunk_index": chunk["chunk_index"],
                "content_hash": chunk["content_hash"],
            },
        )
        points.append(point)
        stored_chunks.append(chunk)

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    return stored_chunks
    


def search_vectors(
    tenant_id: str,
    query_vector: list[float],
    top_k: int = 3,
) -> list[dict]:
    """
    搜索相似向量

    参数：
        tenant_id: 租户 ID（只搜该租户的数据，保证隔离）
        query_vector: 查询向量
        top_k: 返回最相似的 N 条

    返回：
        [{"content": "...", "score": 0.95, "document_id": "..."}, ...]
    """
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter={
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}}
            ]
        },
        limit=top_k,
    )

    return [
        {
            "chunk_id": str(point.id),
            "content": point.payload["content"],
            "score": point.score,
            "document_id": point.payload["document_id"],
        }
        for point in results.points
    ]


def delete_vectors(document_id: str) -> None:
    """删除指定文档的所有向量"""
    ensure_collection()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )


def make_int_point_id(tenant_id: str, content_hash: str) -> int:
    """根据 tenant_id + content_hash 生成确定性 Point ID"""
    raw = f"{tenant_id}_{content_hash}".encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return int(digest, 16) % (2**63)
