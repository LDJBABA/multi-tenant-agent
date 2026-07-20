# 多租户智能客服 Agent 系统

基于 RAG 架构的 SaaS 化智能客服系统，支持多租户知识库隔离、动态工具注册和 Agent 推理。

## 核心特性

- **多租户隔离** — 逻辑隔离（tenant_id），每家企业独立的知识库和对话能力
- **智能文档解析** — 支持 DOCX/PDF/MD/TXT，表格结构保留、键值对格式、中文标题识别
- **结构化分片** — 按 title/paragraph/table 分级处理，短段落合并、整表不切分
- **三层去重** — 文件 hash → 内容 hash → Embedding 相似度预检
- **意图路由** — 正则预过滤 + LLM 结构化输出，按 knowledge/chitchat/action/redirect 分发
- **多轮对话** — ConversationSummaryBufferMemory 模式，增量摘要缓存
- **Query Rewrite** — 结合对话历史改写，解决指代消解、省略补全、口语转书面
- **Agent 推理** — LangChain ReAct 循环，数据库驱动的动态工具注册，支持租户级工具隔离
- **RAG 评估** — 自动生成黄金集，计算 Recall@K / MRR，前端可视化报告

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js + TypeScript + Tailwind CSS |
| 后端 | Python + FastAPI + async SQLAlchemy |
| 数据库 | PostgreSQL |
| 向量库 | Qdrant |
| LLM | OpenAI 兼容 |
| Agent | LangChain |
| 部署 | Docker Compose |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/LDJBABA/multi-tenant-agent.git
cd multi-tenant-agent
```

### 2. 启动基础设施

```bash
docker compose up -d
```

启动 PostgreSQL + Qdrant + Redis。

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# LLM（百炼）
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# Embedding
EMBEDDING_API_KEY=your-api-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3

# 应用
APP_SECRET_KEY=your-secret-key
```

### 4. 后端

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

后端运行在 `http://127.0.0.1:8000`

### 5. 前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:3000`

## 项目结构

```
multi-tenant-agent/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # API 路由
│   │   ├── core/                # 配置、安全、数据库
│   │   ├── models/              # SQLAlchemy 数据模型
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── services/            # 业务逻辑层
│   │   ├── rag/                 # RAG 管线（解析、分片、向量存储）
│   │   ├── agents/              # Agent 定义、Prompt 模板、Tool 工厂
│   │   ├── integrations/        # LLM 客户端
│   │   └── utils/               # 工具函数
│   ├── alembic/                 # 数据库迁移
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── login/           # 登录页
│       │   ├── register/        # 注册页
│       │   └── dashboard/       # 主控制台（文档/对话/评估/工具）
│       ├── lib/api.ts           # API 客户端
│       └── components/          # 通用组件
├── docker-compose.yml
└── .env.example
```

## 架构

```
用户提问
  → 意图路由（正则预过滤 + LLM 结构化输出）
  ├─ knowledge → Query Rewrite → Embedding → Qdrant 检索 → LLM 回答
  ├─ chitchat  → 直接 LLM 回答
  ├─ action    → 动态加载工具 → Agent ReAct 推理 → 工具调用 → 综合回答
  └─ redirect  → 转人工
```

## API 文档

启动后端后访问 `http://127.0.0.1:8000/docs` 查看 Swagger 文档。

## License

MIT
