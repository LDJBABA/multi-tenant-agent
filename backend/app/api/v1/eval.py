"""
评估相关 API 路由

接口清单：
  POST /api/v1/eval/generate-golden-set  生成黄金集
  GET  /api/v1/eval/golden-sets           黄金集列表
  GET  /api/v1/eval/golden-sets/{file}    黄金集详情
  POST /api/v1/eval/run-evaluation        执行评估
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.eval import (
    GoldenSetRequest,
    GoldenSetListResponse,
    EvalRequest,
    EvalResponse,
)
from app.services import eval_service

router = APIRouter(prefix="/eval", tags=["评估"])


@router.post("/generate-golden-set")
async def generate_golden_set(
    data: GoldenSetRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    生成黄金集

    - 从知识库 chunk 自动生成测试问题
    - 每个问题对应多个 chunk（2-3 个）
    - 保存为 JSON 文件
    """
    result = await eval_service.save_golden_set(
        tenant_id=current_tenant.id,
        num_chunks=data.num_chunks,
    )
    return {
        "file_path": result["file_path"],
        "question_count": result["question_count"],
        "message": "黄金集已生成",
    }


@router.get("/golden-sets", response_model=GoldenSetListResponse)
async def list_golden_sets(
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """获取当前租户的黄金集列表"""
    golden_sets = eval_service.list_golden_sets(current_tenant.id)
    return {"golden_sets": golden_sets, "total": len(golden_sets)}


@router.get("/golden-sets/{filename}")
async def get_golden_set(
    filename: str,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """获取指定黄金集的详细内容"""
    from pathlib import Path

    file_path = Path("eval") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="黄金集文件不存在")

    # 验证文件属于当前租户
    if not filename.startswith(f"golden_set_{current_tenant.id[:8]}"):
        raise HTTPException(status_code=403, detail="无权访问此黄金集")

    data = eval_service.load_golden_set(str(file_path))
    return {"filename": filename, "items": data}


@router.post("/run-evaluation", response_model=EvalResponse)
async def run_evaluation(
    data: EvalRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    执行 RAG 评估

    - quick 模式：只评估 Recall@K + MRR（秒出）
    - full 模式：评估 Recall@K + MRR + Faithfulness + Relevance（需要几分钟）
    """
    # 验证文件存在
    from pathlib import Path
    file_path = Path(data.golden_set_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="黄金集文件不存在")

    report = await eval_service.run_evaluation(
        tenant_id=current_tenant.id,
        golden_set_path=data.golden_set_path,
        top_k=data.top_k,
        mode=data.mode,
    )

    if "error" in report:
        raise HTTPException(status_code=400, detail=report["error"])

    return report
