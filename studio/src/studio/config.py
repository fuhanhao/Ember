from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://studio:studio@postgres:5432/studio"
    database_url_sync: str = "postgresql+psycopg2://studio:studio@postgres:5432/studio"

    # Redis
    redis_url: str = "redis://redis:6379/4"

    # Celery
    celery_broker_url: str = "redis://redis:6379/5"
    celery_result_backend: str = "redis://redis:6379/6"

    # Mine API
    mine_api_url: str = "http://mine-api:8000/mine/v1"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://aihubmix.com/v1"
    llm_model: str = "gemini-3.1-pro-preview-search"
    llm_model_light: str = "gemini-3.1-flash-lite-preview"
    embedding_model: str = "text-embedding-3-small"
    briefing_api_key: str = ""
    briefing_model: str = "gemini-3.1-flash-lite-preview"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # JWT
    jwt_secret: str = "forge-studio-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    # App
    app_name: str = "FORGE Studio"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
