from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # Redis (for temporary execution tracking and WebSocket management)
    redis_url: str = Field(..., alias="CODE_EXECUTION_REDIS_URL")
    
    # Code Execution Service (Third-party API)
    code_execution_api_url: str = Field(..., alias="CODE_EXECUTION_API_URL")
    code_execution_api_key: str  = Field(..., alias="CODE_EXECUTION_API_KEY")
    
    # Frontend Service (for WebSocket callbacks)
    frontend_service_url: str = Field(..., alias="FRONTEND_SERVICE_URL")
    
    # Service Config
    host: str = Field(..., alias="CODE_EXECUTION_HOST")
    port: int = Field(..., alias="CODE_EXECUTION_PORT")
    debug: bool = Field(..., alias="CODE_EXECUTION_DEBUG")
    
    # Execution tracking TTL (seconds)
    execution_ttl: int = 3600  # 1 hour


settings = Settings()
