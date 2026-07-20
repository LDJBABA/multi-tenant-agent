"""
对话业务逻辑层

流程：问题 → Embedding → 检索相关 chunk → 拼 prompt → LLM 回答 → 保存消息
"""

import json
import uuid
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Session, Message
from app.models.tenant import Tenant
from app.integrations.llm_client import embed_query, chat, intent_llm
from app.rag.vector_store import search_vectors
from app.agents.prompts import CUSTOMER_SERVICE_PROMPT, INTENT_ROUTER_PROMPT, SUMMARY_PROMPT, REWRITE_QUERY_PROMPT

from app.core.config import settings
from app.utils.common_utils import count_tokens
import logging

logger = logging.getLogger(__name__)


async def ask(
    db: AsyncSession,
    tenant: Tenant,
    question: str,
    session_id: str | None = None,
) -> dict:
    """
    处理用户提问

    返回：{"answer": "...", "session_id": "...", "retrieved_chunks": [...]}
    """
    # 获取或创建会话
    if session_id:
        session = await get_or_create_session(db, tenant.id, session_id)
    else:
        session = await create_session(db, tenant.id)

    history = await get_message_history(db, session)
    
    # 意图路由（替换原来的 rewrite_query）
    route = await intent_router(question, history)
    logger.info(f"意图路由=============route: {route}")
    intent = route["intent"]
    rewritten = route["rewritten"]
    params = route["params"]

    results = []
    # 分发
    if intent == "chitchat":
        system_prompt = CUSTOMER_SERVICE_PROMPT.format(agent_name=tenant.name, context="")
        answer = await chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": rewritten},
        ])
    elif intent == "redirect":
        answer = "正在为您转接人工客服，请稍候..."
    elif intent == "action":
        from app.services.agent_service import run_agent
        answer = await run_agent(db, tenant.id, rewritten)
    else:  # knowledge
        # # 问题 Embedding
        query_vector = await embed_query(rewritten)
        # 检索相关 chunk（强制按租户过滤）
        results = search_vectors(tenant.id, query_vector, top_k=5)
        context = "\n\n".join([r["content"] for r in results])
        system_prompt = CUSTOMER_SERVICE_PROMPT.format(agent_name=tenant.name, context=context)
        # 构建消息体
        messages = await build_messages_with_memory(
                system_prompt=system_prompt,
                session=session,
                current_question=question, 
                db=db,
                history=history
            )
        answer = await chat(messages)

    

    # 保存用户消息
    user_message = Message(
        session_id=session.id,
        role="user",
        content=question,
        token_count=count_tokens(question),
    )
    db.add(user_message)
    await db.commit()

    # 保存 AI 回答
    ai_message = Message(
        session_id=session.id,
        role="assistant",
        content=answer,
        token_count=count_tokens(answer),
    )
    db.add(ai_message)
    await db.commit()

    return {
        "answer": answer,
        "session_id": session.id,
        "retrieved_chunks": [r["content"] for r in results],
        "retrieved_scores": [round(r["score"], 4) for r in results],  # 新增
    }


async def build_messages_with_memory(
    system_prompt: str,
    session: Session,
    current_question: str,
    db: AsyncSession,
    history: list[Message],
) -> list[dict]:
    """
    构建包含历史消息的对话消息列表
    """
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    
#   计算历史消息的 token 总数
    history_tokens = sum(msg.token_count for msg in history)

    if history_tokens <= settings.max_token_limit:
        # 不超限，直接用全部历史
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
    else:
        # 超限，使用摘要 + 最近 N 条
        summary, summary_count = await get_or_generate_summary(db, session, history)

        # 摘要作为 system 消息
        messages.append({
            "role": "system",
            "content": f"以下是早期对话的摘要：\n{summary}"
        })

        # 最近 N 条保留原文（从摘要结束处开始）
        recent_messages = history[summary_count:]
        for msg in recent_messages:
            messages.append({"role": msg.role, "content": msg.content})

    # 加上当前问题
    messages.append({"role": "user", "content": current_question})

    return messages

async def get_or_generate_summary(
    db: AsyncSession,
    session: Session,
    history: list[Message],
) -> tuple[str, int]:
    """
    获取缓存的摘要，或生成新摘要

    缓存策略：
    - 有缓存且新增消息 < 5 条 → 直接用旧摘要
    - 无缓存或新增消息 ≥ 5 条 → 生成新摘要

    返回：(摘要文本, 摘要覆盖的消息条数)
    """
    summary_count = session.summary_count or 0
    new_count = len(history) - summary_count
    # 摘要应覆盖到"最近 N 条"之前
    target_count = max(0, len(history) - settings.recent_count)

    #动态计算阈值：recent_count 的一半
    summary_update_threshold = max(1, settings.recent_count // 2)
    # 有缓存且新增不多，直接返回
    if session.summary and new_count < summary_update_threshold:
        return session.summary, summary_count

    # 需要生成摘要
    if session.summary:
        # 增量：旧摘要 + 新消息（只到 target_count，不含最近 N 条）
        new_msgs = history[summary_count:target_count]
        new_text = "\n".join(f"{m.role}: {m.content}" for m in new_msgs)
        prompt_text = f"旧摘要：\n{session.summary}\n\n新增对话：\n{new_text}"
    else:
        # 全量：只到 target_count
        msgs_to_summarize = history[:target_count]
        prompt_text = "\n".join(f"{m.role}: {m.content}" for m in msgs_to_summarize)

    summary = await chat([
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content": prompt_text},
    ])
    logger.info(f"生成会话摘要>>>>>>>: {summary}")

    # 缓存到 session
    session.summary = summary
    session.summary_count = target_count
    await db.commit()

    return summary, target_count
async def get_message_history(db, session) -> list[Message]:
    """获取会话历史消息"""
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at)
        # .limit(settings.history_limit)
    )
    history = history_result.scalars().all()
    return history


async def create_session(db: AsyncSession, tenant_id: str) -> Session:
    """创建新会话"""
    session = Session(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id="anonymous",  # MVP 阶段暂用匿名
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_or_create_session(
    db: AsyncSession, tenant_id: str, session_id: str
) -> Session:
    """获取已有会话，不存在则创建"""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        session = await create_session(db, tenant_id)

    return session


async def list_sessions(db: AsyncSession, tenant_id: str) -> list[Session]:
    """查询当前租户的所有会话，按创建时间倒序"""
    result = await db.execute(
        select(Session)
        .where(Session.tenant_id == tenant_id)
        .order_by(Session.created_at.desc())
    )
    return list(result.scalars().all())


async def get_session_messages(
    db: AsyncSession, session_id: str, tenant_id: str
) -> list[Message]:
    """查询指定会话的所有消息"""
    # 验证会话归属
    session_result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == tenant_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise ValueError("会话不存在")

    # 查询消息
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())

async def rewrite_query(
    db: AsyncSession,
    session: Session,
    current_query: str,
    max_history_turns: int = 3,
    history: list[Message] = None,
) -> str:
    """
    多轮改写：结合对话历史，将用户问题改写为独立、书面化的检索查询
    
    逻辑：
    1. 取最近 N 轮对话历史
    2. 如果没有历史，直接返回原 query
    3. 有历史则调 LLM 改写
    """
    
    # 无历史，不需要改写
    if not history:
        return current_query
    
    # 取最近 max_history_turns * 2 条（每轮=user+assistant）
    recent = history[-(max_history_turns * 2):]
    history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
    
    prompt = REWRITE_QUERY_PROMPT.format(
        max_history_turns=max_history_turns,
        history_text=history_text,
        current_query=current_query,
    )
    
    rewritten = await chat([{"role": "user", "content": prompt}])
    logger.info(f"""Query Rewrite结果: [{current_query}] → [{rewritten}]""")
    
    return rewritten.strip()

async def intent_router(query: str, history: list[Message]) -> dict:
    """
    意图识别 + 改写 + 参数提取（一次 LLM 调用）
    
    返回：{"intent": "knowledge|chitchat|action|redirect", "rewritten": "...", "params": {}}
    """
    # 第一档：正则预过滤
    if is_greeting(query):
        return {"intent": "chitchat", "rewritten": query, "params": {}}
    if is_transfer(query):
        return {"intent": "redirect", "rewritten": query, "params": {}}
    
    # 第二档：LLM 合并调用
    recent = history[-6:]  # 最近3轮
    history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
    
    inputs = [
        {"role": "system", "content": INTENT_ROUTER_PROMPT},
        {"role": "user", "content": f"对话历史：\n{history_text}\n\n用户问题：{query}"},
    ]
    logger.info(f"意图识别输入>>>>>>>: {inputs}")
    # 调用意图识别 LLM
    result = await intent_llm.ainvoke(inputs)
    logger.info(f"意图识别结果>>>>>>>: {result}")
    
    # result 已经是 IntentResult 对象
    return {
        "intent": result.intent,
        "rewritten": result.rewritten,
        "params": result.params,
    }


GREETING_PATTERNS = re.compile(r"^(你好|hi|hello|嗨|谢谢|thanks|拜拜|再见|bye)$", re.IGNORECASE)
TRANSFER_PATTERNS = re.compile(r"(转人工|人工客服|投诉|不满意|要投诉)")

def is_greeting(query: str) -> bool:
    return bool(GREETING_PATTERNS.match(query.strip()))

def is_transfer(query: str) -> bool:
    return bool(TRANSFER_PATTERNS.search(query))
