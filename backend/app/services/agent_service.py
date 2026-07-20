from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.tool_config import ToolConfig
from app.agents.tool_factory import create_dynamic_tool
from app.integrations.llm_client import get_llm
from langchain.agents import create_agent
from langchain_core.callbacks import StdOutCallbackHandler
import logging

logger = logging.getLogger(__name__)

async def load_tenant_tools(db: AsyncSession, tenant_id: str) -> list:
    """从数据库加载租户的工具配置"""
    result = await db.execute(
        select(ToolConfig).where(
            ToolConfig.tenant_id == tenant_id,
            ToolConfig.is_active == True,
        )
    )
    configs = result.scalars().all()
    
    tools = []
    for config in configs:
        tool = create_dynamic_tool({
            "name": config.name,
            "description": config.description,
            "endpoint": config.endpoint,
            "method": config.method,
            "auth_type": config.auth_type,
            "auth_config": config.auth_config,
        })
        tools.append(tool)
    
    return tools

async def run_agent(db: AsyncSession, tenant_id: str, question: str) -> str:
    """加载租户工具，执行 Agent"""
    tools = await load_tenant_tools(db, tenant_id)
    
    if not tools:
        return "当前没有可用的工具，请联系管理员配置。"
    
    logger.info(f"Agent 加载 {len(tools)} 个工具: {[(t.name, t.description) for t in tools]}")
    logger.info(f"Agent 输入: {question}")

    llm = get_llm("mimo")
    agent = create_agent(llm, tools)
    
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": question}]
    },config={"callbacks": [StdOutCallbackHandler()]}
    )
    
    return result["messages"][-1].content
