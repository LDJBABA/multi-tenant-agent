# RAG 评估功能设计文档

> 创建日期：2026-07-06
> 状态：已审核

---

## 1. 背景与目标

### 背景

项目已实现 RAG 基础链路（文档上传 → 解析切分 → Embedding → 检索 → LLM 生成），但缺乏量化评估手段，无法衡量检索质量和回答质量。

### 目标

提供一个开发调试用的 RAG 评估功能，支持：
- 从知识库自动生成测试问题集（黄金集）
- 对 RAG 系统进行量化评估
- 可视化展示评估结果

### 使用场景

开发者手动触发，查看评估报告，调优 RAG 参数。

---

## 2. 功能概述

### 核心流程

```
Step 1: 生成黄金集
  ├── 输入：chunk 数量（默认 10）
  ├── 操作：精选 chunk → 按文档分组 → 多 chunk 联合生成问题
  └── 输出：黄金集 JSON 文件（每个问题对应多个 chunk）

Step 2: 执行评估
  ├── 输入：黄金集文件 + 评估模式
  ├── 操作：对每个问题执行 RAG 检索 + 可选生成评估
  └── 输出：评估报告

Step 3: 查看报告
  ├── 汇总卡片：指标平均值
  ├── 明细表格：每个问题的详细结果
  └── 展开详情：检索到的 chunk + LLM 回答
```

### 评估指标

| 指标 | 说明 | 需要 LLM |
|------|------|----------|
| Recall@K | 检索到的 chunk 是否包含期望的 chunk | ❌ |
| MRR | 期望的 chunk 排在第几位 | ❌ |
| Faithfulness | 回答是否基于检索到的内容 | ✅ |
| Relevance | 回答是否和问题相关 | ✅ |

### 评估模式

| 模式 | 包含指标 | LLM 调用 | 速度 |
|------|----------|----------|------|
| 快速模式 | Recall@K + MRR | 0 次 | 秒出 |
| 完整模式 | Recall@K + MRR + Faithfulness + Relevance | 2N 次 | 分钟级 |

---

## 3. 数据结构

### 黄金集格式

```json
[
  {
    "query": "退货政策和运费规则是什么？",
    "expected_chunk_ids": ["chunk_id_1", "chunk_id_2"],
    "category": "退货",
    "note": ""
  }
]
```

**说明**：每个问题对应多个 chunk（2-3 个），因为真实场景中用户问题可能需要综合多个知识片段才能完整回答。

### 黄金集生成逻辑

```
获取租户的 chunk
  ↓
按 document_id 分组
  ↓
每组取 2-3 个代表性 chunk
  ↓
多 chunk 联合上下文 → LLM 生成需要综合多段内容的问题
  ↓
每个问题的 expected_chunk_ids 包含所有相关 chunk
```

### 评估请求

```json
{
  "golden_set_path": "eval/golden_set_xxx.json",
  "top_k": 3,
  "mode": "quick"
}
```

### 评估响应

#### 快速模式

```json
{
  "mode": "quick",
  "total_questions": 20,
  "avg_recall_at_k": 0.75,
  "avg_mrr": 0.82,
  "details": [
    {
      "query": "退货几天到账",
      "expected_chunk_ids": ["chunk_1"],
      "retrieved_chunk_ids": ["chunk_1", "chunk_3", "chunk_5"],
      "recall_at_k": 1.0,
      "mrr": 1.0
    }
  ]
}
```

#### 完整模式

```json
{
  "mode": "full",
  "total_questions": 20,
  "avg_recall_at_k": 0.75,
  "avg_mrr": 0.82,
  "avg_faithfulness": 0.91,
  "avg_relevance": 0.88,
  "details": [
    {
      "query": "退货几天到账",
      "expected_chunk_ids": ["chunk_1"],
      "retrieved_chunk_ids": ["chunk_1", "chunk_3", "chunk_5"],
      "recall_at_k": 1.0,
      "mrr": 1.0,
      "faithfulness": 0.95,
      "relevance": 0.98,
      "answer": "根据政策，退货款项将在3-7个工作日内到账...",
      "retrieved_chunks": ["chunk内容1", "chunk内容2", "chunk内容3"]
    }
  ]
}
```

### 黄金集列表响应

```json
{
  "golden_sets": [
    {
      "filename": "golden_set_bdeef48a.json",
      "path": "eval/golden_set_bdeef48a.json",
      "question_count": 3,
      "created_at": "2026-07-06T16:00:00"
    }
  ]
}
```

---

## 4. API 设计

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/eval/generate-golden-set` | POST | 生成黄金集 |
| `/api/v1/eval/golden-sets` | GET | 获取黄金集列表 |
| `/api/v1/eval/golden-sets/{filename}` | GET | 获取黄金集详情 |
| `/api/v1/eval/run-evaluation` | POST | 执行评估 |

### 接口详情

#### POST /api/v1/eval/generate-golden-set

生成黄金集并保存为 JSON 文件。

**请求体**：
```json
{
  "num_chunks": 10
}
```

**说明**：输入 chunk 数量而非问题数量。系统精选 num_chunks 个代表性 chunk，按文档分组后多 chunk 联合生成问题，每个问题对应 2-3 个 chunk。

**响应**：
```json
{
  "file_path": "eval/golden_set_bdeef48a.json",
  "question_count": 3,
  "message": "黄金集已生成"
}
```

#### GET /api/v1/eval/golden-sets

获取已生成的黄金集列表。

**响应**：
```json
{
  "golden_sets": [...]
}
```

#### GET /api/v1/eval/golden-sets/{filename}

获取指定黄金集的详细内容。

**响应**：
```json
{
  "filename": "golden_set_bdeef48a.json",
  "items": [...]
}
```

#### POST /api/v1/eval/run-evaluation

执行 RAG 评估。

**请求体**：
```json
{
  "golden_set_path": "eval/golden_set_bdeef48a.json",
  "top_k": 3,
  "mode": "quick"
}
```

**响应**：评估报告（格式见第 3 节）。

---

## 5. 后端实现

### 文件结构

```
backend/app/
├── api/v1/eval.py          # 路由（已有，需扩展）
├── schemas/eval.py         # 请求/响应格式（已有，需扩展）
└── services/eval_service.py # 评估逻辑（已有，需重写）
```

### 核心函数

#### eval_service.py

```python
# 黄金集相关
def get_tenant_chunks(tenant_id, limit) -> list[dict]
def group_by_document(chunks) -> dict[str, list[dict]]
def select_chunk_groups(doc_groups, num_chunks) -> list[list[dict]]
async def generate_golden_set(tenant_id, num_chunks) -> list[dict]
async def save_golden_set(tenant_id, num_chunks) -> str

# 评估相关
def load_golden_set(file_path) -> list[dict]
def list_golden_sets(tenant_id) -> list[dict]

async def evaluate_single(query, expected_chunk_ids, tenant_id, top_k, mode) -> dict
async def evaluate_faithfulness_and_relevance(query, answer, contexts) -> tuple[float, float]
async def run_evaluation(tenant_id, golden_set_path, top_k, mode) -> dict
```

### LLM 调用优化

| 优化点 | 实现方式 |
|--------|----------|
| 黄金集复用 | 选择已有文件，不重复生成 |
| 合并评估 | Faithfulness + Relevance 一个 prompt |
| 按需评估 | 快速模式跳过 LLM 调用 |
| 并发执行 | asyncio.gather 并发调用 |

---

## 6. 前端实现

### 页面结构

在 Dashboard 加一个 Tab "评估"。

### 交互流程

```
Step 1: 生成黄金集
  ├── 输入：chunk 数量（默认 10）
  ├── 按钮：[生成黄金集]
  └── 结果：显示生成的文件路径和问题数量

Step 2: 执行评估
  ├── 选择：黄金集文件下拉框
  ├── 输入：Top-K（默认 3）
  ├── 选择：评估模式（快速/完整）
  ├── 按钮：[开始评估]
  └── 结果：显示进度（完整模式）

Step 3: 查看报告
  ├── 汇总卡片：4 个指标的平均值
  ├── 明细表格：每个问题的详细结果
  └── 展开详情：点击行展开，显示检索 chunk + LLM 回答
```

### 组件结构

```
dashboard/page.tsx
├── Tab: 评估
│   ├── GoldenSetGenerator    # Step 1
│   ├── EvaluationRunner      # Step 2
│   └── EvaluationReport      # Step 3
│       ├── MetricCards       # 汇总卡片
│       ├── ResultTable       # 明细表格
│       └── DetailExpand      # 展开详情
```

---

## 7. 成本分析

### 快速模式

| 步骤 | LLM 调用 |
|------|----------|
| 检索 | 0 次（纯向量检索） |
| 评估 | 0 次 |
| **总计** | 0 次 |

### 完整模式（20 个问题）

| 步骤 | LLM 调用 |
|------|----------|
| 生成回答 | 20 次 |
| 评估质量 | 20 次（合并后） |
| **总计** | 40 次 |

---

## 8. 依赖

### 后端

- 已有：FastAPI, SQLAlchemy, Qdrant, LLM Client
- 新增：无

### 前端

- 已有：React, Next.js, Tailwind
- 新增：无

---

## 9. 风险与限制

| 风险 | 说明 | 应对 |
|------|------|------|
| LLM 评估不稳定 | Faithfulness/Relevance 评分可能波动 | 多次评估取平均 |
| 黄金集质量 | LLM 生成的问题可能不准确 | 支持手动编辑黄金集 |
| 并发限制 | 百炼 API 可能有并发限制 | 控制并发数 |

---

## 10. 后续扩展

| 功能 | 说明 |
|------|------|
| 手动编辑黄金集 | 支持在前端修改问题和期望 chunk |
| 评估历史 | 保存评估结果，对比不同版本 |
| 自动评估 | 上传文档后自动跑一轮评估 |
| 指标可视化 | 图表展示指标分布和趋势 |
