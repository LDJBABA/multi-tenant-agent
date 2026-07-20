"""快速测试 Embedding 和 LLM 是否可用"""

import asyncio
from app.integrations.llm_client import embed_query, chat


async def main():
    # 测试 Embedding
    print("=== 测试 Embedding ===")
    try:
        vector = await embed_query("你好，我是测试文本")
        print(f"✅ Embedding 成功，向量维度：{len(vector)}")
        print(f"   前5个值：{vector[:5]}")
    except Exception as e:
        print(f"❌ Embedding 失败：{e}")

    # 测试 LLM
    print("\n=== 测试 LLM ===")
    try:
        answer = await chat([{"role": "user", "content": "用一句话介绍你自己"}])
        print(f"✅ LLM 成功")
        print(f"   回答：{answer}")
    except Exception as e:
        print(f"❌ LLM 失败：{e}")


asyncio.run(main())
