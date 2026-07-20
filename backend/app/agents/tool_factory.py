import httpx
from langchain_core.tools import StructuredTool, tool
import logging

logger = logging.getLogger(__name__)

def create_dynamic_tool(config: dict):
    """根据数据库配置动态生成 Tool"""
    name = config["name"]
    description = config["description"]
    endpoint = config["endpoint"]
    method = config.get("method", "POST")
    auth_type = config.get("auth_type", "none")
    auth_config = config.get("auth_config", {})
    
    def build_headers() -> dict:
        headers = {"Content-Type": "application/json"}
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        elif auth_type == "api_key":
            headers["X-API-Key"] = auth_config.get("api_key", "")
        return headers
    
    def tool_func(**kwargs) -> str:
        """{description}"""
        try:
            response = httpx.request(
                method=method,
                url=endpoint,
                json=kwargs,
                headers=build_headers(),
                timeout=10.0,
            )
            return response.text
        except Exception as e:
            logger.error(f"工具 {name} 调用失败: {e}")
            return f"工具调用失败: {str(e)}"
    
    # 用 StructuredTool 显式指定 name 和 description
    return StructuredTool.from_function(
        func=tool_func,
        name=name,
        description=description,
    )
