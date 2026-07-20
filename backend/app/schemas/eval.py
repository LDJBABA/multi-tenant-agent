"""
评估相关接口的请求/响应数据格式
"""

from pydantic import BaseModel


class GoldenSetRequest(BaseModel):
    """黄金集生成请求"""
    num_chunks: int = 10  # 使用的 chunk 数量


class GoldenSetItem(BaseModel):
    """黄金集单项"""
    query: str
    expected_chunk_ids: list[str]
    category: str = ""
    note: str = ""


class GoldenSetListResponse(BaseModel):
    """黄金集列表响应"""
    golden_sets: list[dict]
    total: int


class EvalRequest(BaseModel):
    """评估请求"""
    golden_set_path: str      # 黄金集文件路径
    top_k: int = 3            # 检索 top-k
    mode: str = "quick"       # quick=只评估检索，full=评估检索+生成质量


class EvalResponse(BaseModel):
    """评估响应"""
    mode: str
    total_questions: int
    avg_recall_at_k: float
    avg_mrr: float
    avg_faithfulness: float = 0.0
    avg_relevance: float = 0.0
    details: list[dict]
