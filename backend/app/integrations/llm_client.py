"""
LLM 客户端（兼容 OpenAI 接口规范）

Embedding 和 LLM 可以用不同服务商
只需在 .env 里分别配置 base_url 和 api_key
"""
import logging
import json

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from app.schemas.intent import IntentResult
from app.core.config import settings
from langchain_qwq import ChatQwen
from app.schemas.intent import IntentResult

logger = logging.getLogger(__name__)

# Embedding 客户端
embedding_client = AsyncOpenAI(
    api_key=settings.embedding_api_key,
    base_url=settings.embedding_base_url,
)

# LLM 客户端
llm_client = AsyncOpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)

# 意图识别 LLM（普通模式，不用 with_structured_output，百炼不支持）
intent_llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
).with_structured_output(IntentResult, method="json_mode")

def get_llm(provider: str = "mimo") -> ChatOpenAI:
    """统一获取 LLM 实例，方便切换"""
    if provider == "mimo":
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    else:
        raise ValueError(f"不支持的 LLM: {provider}")
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本转向量，自动分批处理（百炼限制单次最多 10 条）"""
    batch_size = 10
    all_vectors = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await embedding_client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        all_vectors.extend([item.embedding for item in response.data])

    return all_vectors


async def embed_query(text: str) -> list[float]:
    """单条文本转向量（查询用）"""
    result = await embed_texts([text])
    return result[0]


async def chat(messages: list[dict]) -> str:
    """对话接口"""
    logger.info(f"LLM 输入>>>>>>>: {messages}")
    response = await llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
    )
    logger.info(f"LLM response输出<<<<<<<: {json.dumps(response.model_dump(), ensure_ascii=False)}")

    # 兼容百炼和 OpenAI 两种返回格式
    answer = ""
    if response.choices:
        answer = response.choices[0].message.content
    else:
        answer = response.text
    return answer
