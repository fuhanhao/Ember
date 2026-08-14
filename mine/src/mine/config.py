from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://mine:mine@postgres:5432/mine"
    database_url_sync: str = "postgresql+psycopg2://mine:mine@postgres:5432/mine"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://aihubmix.com/v1"
    openai_model: str = "gemini-3.1-pro-preview-search"
    openai_model_light: str = "gemini-3.1-flash-lite-preview"

    # GitHub
    github_token: str = ""

    # YouTube (Data API v3, optional - channel RSS works without it)
    youtube_api_key: str = ""

    # Twitter via twitterapi.io (same provider as the n8n aggregator)
    twitterapi_io_key: str = ""

    # RSSHub (local instance used for YouTube/Twitter feeds)
    rsshub_base_url: str = "http://rsshub:1200"
    rsshub_access_key: str = "forge_mine_2026"

    # Jina Reader API (for full-text extraction from JS-rendered sites)
    jina_api_key: str = ""

    # Proxy pool
    # Mode 1 - static list: "socks5://u:p@host:port,http://host:port"
    # Mode 2 - tunnel: "http://tunnel_user:tunnel_pass@tunnel.kuaidaili.com:15818"
    # Mode 3 - API extract: set proxy_api_url, pool auto-refreshes
    proxy_urls: str = ""
    proxy_api_url: str = ""          # e.g. "https://dps.kdlapi.com/api/getdps/?orderid=xxx&num=10&format=json"
    proxy_api_refresh_seconds: int = 60  # re-fetch IPs every N seconds
    proxy_api_protocol: str = "http"     # protocol prefix for extracted IPs

    # Rate limiting (default: 5 requests per 10 seconds per domain)
    rate_limit_requests: int = 5
    rate_limit_window: int = 10

    # App
    app_name: str = "Ember Mine"
    debug: bool = False

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
