"""
配置管理文件，负责从 .env 读取配置。
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库
    database_url: str

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Embedding 配置
    embedding_api_key: str = ""
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "qwen3.7-text-embedding"

    # LLM 配置
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"

    # 应用
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_debug: bool = True

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}

    # 对话上下文配置
    max_token_limit: int = 1000     # 超过这个 token 数触发摘要
    recent_count: int = 3          # 摘要模式下保留最近 N 条原文


settings = Settings()