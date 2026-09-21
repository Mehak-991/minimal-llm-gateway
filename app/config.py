import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError

class Settings(BaseSettings):
    gateway_port: int = 8000
    gateway_env: str = "development"
    
    llm_provider: str = "groq"
    llm_provider_api_key: str = ""
    llm_provider_default_model: str = "openai/gpt-oss-20b"
    llm_provider_timeout: float = 15.0
    
    llm_provider_cost_per_1k_prompt: float = 0.00
    llm_provider_cost_per_1k_completion: float = 0.00
    
    database_url: str = Field(..., description="PostgreSQL Connection URL is required")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

try:
    settings = Settings()
except ValidationError as e:
    print(f"Configuration Error: Missing required environment variables.\n{e}")
    sys.exit(1)
