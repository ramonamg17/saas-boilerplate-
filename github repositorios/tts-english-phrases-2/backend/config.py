"""
config.py — Single source of truth for all runtime settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application identity ──────────────────────────────────────────
    APP_NAME: str = "TTS English Phrases"
    FRONTEND_URL: str = "http://localhost:8000"
    SUPPORT_EMAIL: str = "support@example.com"
    OWNER_EMAIL: str = "you@example.com"

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # ── Auth ──────────────────────────────────────────────────────────
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ── Stripe ────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = "sk_test_placeholder"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_placeholder"
    STRIPE_WEBHOOK_SECRET: str = "whsec_placeholder"
    BILLING_MODE: str = "checkout"

    # ── Email ─────────────────────────────────────────────────────────
    RESEND_API_KEY: str = "re_placeholder"
    EMAIL_FROM: str = "noreply@example.com"

    # ── Feature flags ─────────────────────────────────────────────────
    PAYWALL_MODE: str = "modal"
    ENABLE_GUEST_SESSIONS: bool = True
    GUEST_NUDGE_AFTER: int = 3
    RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # ── TTS App specific ──────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    TTS_SERVICE_URL: str = "http://localhost:8880"
    RUNPOD_API_KEY: str = ""
    RUNPOD_ENDPOINT_ID: str = ""
    TTS_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "audio-sessions"
    SESSION_TTL_HOURS: int = 3
    MAX_GENERATION_TIMEOUT_SECONDS: int = 120
    FRONTEND_ORIGIN: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
