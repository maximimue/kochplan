from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Alle Werte kommen aus Umgebungsvariablen bzw. .env (Listen/Dicts als JSON)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://kochplan:kochplan@localhost:5432/kochplan"
    cors_origins: list[str] = []

    # Auth
    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    jwt_access_ttl_minutes: int = 30
    refresh_ttl_days: int = 60
    apple_audiences: list[str] = []   # iOS Bundle-ID + Services-ID (Web)
    google_audiences: list[str] = []  # OAuth-Client-IDs (iOS + Web)
    dev_login_enabled: bool = False   # nur env=dev, niemals in Production

    # Planung
    default_timezone: str = "Europe/Berlin"
    start_buffer_minutes: int = 10    # Puffer vor Kochbeginn

    # KI
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_timeout_s: float = 90.0
    ai_price_input_per_mtok_usd: float = 3.0    # aktuelle Preise eintragen
    ai_price_output_per_mtok_usd: float = 15.0
    ai_limits_enabled: bool = False   # MVP: aus. Production: an.
    ai_rate_per_minute: int = 10      # gilt immer, auch im MVP
    ai_max_per_plan: int = 7          # max. KI-Rezepte pro Plan-Generierung

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
