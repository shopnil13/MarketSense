import os

from pydantic import field_validator
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

    @field_validator("database_url", "aiml_api_key", "slack_webhook_url", "hitl_api_url",
                     "thenvoi_rest_url", "thenvoi_ws_url", "aiml_model", mode="before")
    @classmethod
    def _strip_whitespace(cls, v):
        # Cloud dashboards (e.g. Railway) often append a trailing newline when pasting env
        # values. A stray "\n" in DATABASE_URL makes the db name "railway\n" -> connection fails.
        return v.strip() if isinstance(v, str) else v


settings = Settings()


def resolve_agent_credentials(role: str) -> tuple[str, str]:
    """Return (agent_id, api_key) for a Band agent role.

    Order of precedence:
    1. Environment variables ``<ROLE>_AGENT_ID`` / ``<ROLE>_API_KEY`` (used in production
       e.g. Railway, where agent_config.yaml is not present — it's gitignored).
    2. ``agent_config.yaml`` via the Band SDK loader (used for local development).
    """
    env_id = os.getenv(f"{role.upper()}_AGENT_ID")
    env_key = os.getenv(f"{role.upper()}_API_KEY")
    if env_id and env_key:
        return env_id.strip(), env_key.strip()

    from band.config.loader import load_agent_config
    return load_agent_config(role)
