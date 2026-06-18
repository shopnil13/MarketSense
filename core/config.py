from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Band / Thenvoi
    thenvoi_rest_url: str = "https://app.band.ai/"
    thenvoi_ws_url: str = "wss://app.band.ai/api/v1/socket/websocket"

    # AI/ML API — powers all 3 agent brains AND the Analyst's bounded narrative call
    aiml_api_key: str = ""
    aiml_model: str = "openai/gpt-4o-mini"

    # Database
    database_url: str = "postgresql+asyncpg://marketsense:marketsense@localhost:5433/marketsense"

    # Notifications
    slack_webhook_url: str = ""
    hitl_api_url: str = "http://localhost:8000"

    # Business rules
    margin_floor_pct: float = 6.0
    max_price_change_pct: float = 15.0
    price_drop_threshold_pct: float = 5.0


settings = Settings()
