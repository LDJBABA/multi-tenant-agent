"""
评估服务

职责：
1. 生成黄金集（从 chunk 生成测试问题）
2. 执行 RAG 评估（检索质量 + 回答质量）
"""

import json
import asyncio
from pathlib import Path

from app.rag.vector_store import client, COLLECTION_NAME, search_vectors
from app.integrations.llm_client import chat, embed_query


def get_tenant_chunks(tenant_id: str, limit: int = 100) -> list[dict]:
    """从 Qdrant 获取租户的 chunk"""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    results = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
            ]
        ),
        limit=limit,
        with_payload=True,
    )

    chunks = []
    for point in results[0]:
        chunks.append({
            "chunk_id": str(point.id),
            "content": point.payload.get("content", ""),
            "document_id": point.payload.get("document_id", ""),
        })

    return chunks


def select_chunk_groups(chunks: list[dict], num_chunks: int, group_size: int = 5) -> list[list[dict]]:
    """
    将 chunk 按固定大小分组

    策略：每 group_size 个 chunk 为一组，不做文档区分
    目的：每个问题只关联 3-5 个 chunk，评估才有区分度
    """
    # 限制总数
    chunks = chunks[:num_chunks]

    # 按固定大小切分
    groups = []
    for i in range(0, len(chunks), group_size):
        group = chunks[i:i + group_size]
        groups.append(group)

    return groups


async def generate_golden_set(tenant_id: str, num_chunks: int = 10) -> list[dict]:
    """
    生成黄金集

    流程：
    1. 获取租户的 chunk
    2. 按固定大小分组（每组 3 个 chunk）
    3. LLM 生成问题并标注每个问题需要哪些 chunk（relevant_indices）
    4. 根据 relevant_indices 精确绑定 expected_chunk_ids
    """
    chunks = get_tenant_chunks(tenant_id, limit=100)
    if not chunks:
        return []

    # 按固定大小分组（每组 3 个 chunk）
    selected_groups = select_chunk_groups(chunks, num_chunks, group_size=3)

    golden_set = []
    # 根据分组数量决定每个分组生成几个问题
    questions_per_group = max(2, 10 // max(1, len(selected_groups)))

    for group in selected_groups:
        # 联合上下文，带编号
        chunk_lines = []
        for i, c in enumerate(group):
            chunk_lines.append(f"[{i}] {c['content'][:300]}")
        combined_content = "\n---\n".join(chunk_lines)

        # 生成问题，并标注需要哪些 chunk
        prompt = f"""根据以下内容，生成 {questions_per_group} 个用户可能会问的问题。

内容（每段前有编号 [0] [1] [2]）：
{combined_content}

要求：
1. 问题应该是自然语言提问
2. 给每个问题分类
3. 标注回答该问题需要哪些 chunk 编号（relevant_indices）

输出格式（严格按此格式，每个问题一行）：
问题：xxx | 分类：xxx | 需要：0,1
问题：xxx | 分类：xxx | 需要：2
问题：xxx | 分类：xxx | 需要：0,2"""

        response = await chat([{"role": "user", "content": prompt}])

        # 解析响应
        for line in response.strip().split("\n"):
            if "问题：" in line and "分类：" in line and "需要：" in line:
                parts = line.split("|")
                if len(parts) == 3:
                    question = parts[0].replace("问题：", "").strip()
                    category = parts[1].replace("分类：", "").strip()
                    indices_str = parts[2].replace("需要：", "").strip()

                    # 解析 relevant_indices
                    try:
                        relevant_indices = [int(x.strip()) for x in indices_str.split(",")]
                        # 过滤越界索引
                        relevant_indices = [i for i in relevant_indices if 0 <= i < len(group)]
                    except ValueError:
                        relevant_indices = list(range(len(group)))  # 解析失败则全选

                    # 根据 relevant_indices 精确绑定 chunk_ids
                    expected_chunk_ids = [group[i]["chunk_id"] for i in relevant_indices]

                    golden_set.append({
                        "query": question,
                        "expected_chunk_ids": expected_chunk_ids,
                        "category": category,
                        "note": "",
                    })

    return golden_set


async def save_golden_set(tenant_id: str, num_chunks: int = 10) -> dict:
    """
    生成黄金集并保存为 JSON 文件

    返回：{file_path, question_count}
    """
    golden_set = await generate_golden_set(tenant_id, num_chunks)

    # 保存到文件
    output_dir = Path("eval")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"golden_set_{tenant_id[:8]}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(golden_set, f, ensure_ascii=False, indent=2)

    return {
        "file_path": str(output_file),
        "question_count": len(golden_set),
    }


def list_golden_sets(tenant_id: str) -> list[dict]:
    """获取租户的黄金集列表"""
    eval_dir = Path("eval")
    if not eval_dir.exists():
        return []

    golden_sets = []
    prefix = f"golden_set_{tenant_id[:8]}"

    for file in eval_dir.glob(f"{prefix}*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            golden_sets.append({
                "filename": file.name,
                "path": str(file),
                "question_count": len(data),
                "created_at": file.stat().st_mtime,
            })
        except (json.JSONDecodeError, IOError):
            continue

    return golden_sets


def load_golden_set(file_path: str) -> list[dict]:
    """加载黄金集文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_recall_at_k(expected_ids: list[str], retrieved_ids: list[str]) -> float:
    """计算 Recall@K"""
    if not expected_ids:
        return 0.0
    expected_set = set(expected_ids)
    retrieved_set = set(retrieved_ids)
    return len(expected_set & retrieved_set) / len(expected_set)


def calculate_mrr(expected_ids: list[str], retrieved_ids: list[str]) -> float:
    """计算 MRR（平均倒数排名）"""
    expected_set = set(expected_ids)
    for i, chunk_id in enumerate(retrieved_ids):
        if chunk_id in expected_set:
            return 1.0 / (i + 1)
    return 0.0


async def evaluate_faithfulness_and_relevance(
    query: str, answer: str, contexts: list[str]
) -> tuple[float, float]:
    """
    一次调用同时评估忠实度和相关性

    返回：(faithfulness, relevance)
    """
    context_text = "\n".join(contexts[:3])  # 最多取 3 个 chunk
    prompt = f"""评估以下回答的质量。

问题：{query}
参考资料：{context_text}
回答：{answer}

请输出两个分数（0~1），用逗号分隔：
1. 忠实度（回答是否基于参考资料，1=完全忠实，0=完全编造）
2. 相关性（回答是否解答了问题，1=完全相关，0=完全无关）

只输出两个数字，不要解释："""

    response = await chat([{"role": "user", "content": prompt}])

    try:
        parts = response.strip().split(",")
        faithfulness = float(parts[0].strip())
        relevance = float(parts[1].strip())
        return faithfulness, relevance
    except (ValueError, IndexError):
        return 0.5, 0.5


async def evaluate_single(
    query: str,
    expected_chunk_ids: list[str],
    tenant_id: str,
    top_k: int = 3,
    mode: str = "quick",
) -> dict:
    """
    评估单个问题

    mode="quick": 只评估 Recall@K + MRR
    mode="full": 评估 Recall@K + MRR + Faithfulness + Relevance
    """
    # 检索
    query_vector = await embed_query(query)
    results = search_vectors(tenant_id, query_vector, top_k=top_k)
    retrieved_chunk_ids = [r.get("chunk_id", "") for r in results]
    retrieved_contents = [r["content"] for r in results]

    # 计算检索指标
    recall_at_k = calculate_recall_at_k(expected_chunk_ids, retrieved_chunk_ids)
    mrr = calculate_mrr(expected_chunk_ids, retrieved_chunk_ids)

    result = {
        "query": query,
        "expected_chunk_ids": expected_chunk_ids,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "recall_at_k": round(recall_at_k, 4),
        "mrr": round(mrr, 4),
    }

    # 完整模式：生成回答 + 评估质量
    if mode == "full":
        # 生成回答
        context = "\n\n".join(retrieved_contents)
        answer = await chat([
            {"role": "system", "content": f"基于以下资料回答问题，不要编造：\n{context}"},
            {"role": "user", "content": query},
        ])

        # 评估忠实度和相关性
        faithfulness, relevance = await evaluate_faithfulness_and_relevance(
            query, answer, retrieved_contents
        )

        result["answer"] = answer
        result["retrieved_chunks"] = retrieved_contents
        result["faithfulness"] = round(faithfulness, 4)
        result["relevance"] = round(relevance, 4)

    return result


async def run_evaluation(
    tenant_id: str,
    golden_set_path: str,
    top_k: int = 3,
    mode: str = "quick",
) -> dict:
    """
    执行完整评估

    流程：
    1. 加载黄金集
    2. 对每个问题执行评估（并发）
    3. 汇总指标
    """
    # 加载黄金集
    golden_set = load_golden_set(golden_set_path)

    if not golden_set:
        return {"error": "黄金集为空"}

    # 分批评估（每批 3 个，避免 embedding API 限流）
    tasks = [
        evaluate_single(
            query=item["query"],
            expected_chunk_ids=item["expected_chunk_ids"],
            tenant_id=tenant_id,
            top_k=top_k,
            mode=mode,
        )
        for item in golden_set
    ]
    batch_size = 3
    results = []
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        results.extend(await asyncio.gather(*batch))

    # 汇总指标
    total = len(results)
    avg_recall = sum(r["recall_at_k"] for r in results) / total
    avg_mrr = sum(r["mrr"] for r in results) / total

    report = {
        "mode": mode,
        "total_questions": total,
        "avg_recall_at_k": round(avg_recall, 4),
        "avg_mrr": round(avg_mrr, 4),
        "details": results,
    }

    # 完整模式额外指标
    if mode == "full":
        avg_faithfulness = sum(r.get("faithfulness", 0) for r in results) / total
        avg_relevance = sum(r.get("relevance", 0) for r in results) / total
        report["avg_faithfulness"] = round(avg_faithfulness, 4)
        report["avg_relevance"] = round(avg_relevance, 4)

    return report
