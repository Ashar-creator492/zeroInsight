# Environment-backed settings for database, model, and application security.
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load backend configuration from the environment without putting secrets in the frontend.
class Settings(BaseSettings):
    database_url: str
    groq_api_key: str | None = None
    admin_token: SecretStr | None = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    groq_model: str = "openai/gpt-oss-20b"
    frontend_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
