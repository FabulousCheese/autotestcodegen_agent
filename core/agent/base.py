"""Agent 测试助手 - 核心配置"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """应用配置"""
    
    # API 配置
    app_name: str = "Agent 测试助手"
    debug: bool = True
    
    # DeepSeek LLM 配置
    deepseek_api_key: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    
    # RAG 配置 (已禁用)
    chroma_persist_directory: str = "./data/chroma_db"
    
    # Agent 配置
    max_retries: int = 3
    execution_timeout: int = 300
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
