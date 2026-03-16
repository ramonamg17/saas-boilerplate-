"""
config.py — Single source of truth for all runtime settings.

Lines marked  # EDIT PER PROJECT  should be changed for each new project.
Everything else can stay as-is.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application identity ──────────────────────────────────────────
    APP_NAME: str = "My SaaS App"          # EDIT PER PROJECT
    FRONTEND_URL: str = "http://localhost:3000"
    SUPPORT_EMAIL: str = "support@example.com"  # EDIT PER PROJECT
    OWNER_EMAIL: str = "you@example.com"        # EDIT PER PROJECT

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # ── Auth ──────────────────────────────────────────────────────────
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080        # 7 days

    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/auth/google/callback"

    # ── Stripe ───────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = "sk_test_placeholder"   # EDIT PER PROJECT
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_placeholder"  # EDIT PER PROJECT
    STRIPE_WEBHOOK_SECRET: str = "whsec_placeholder"     # EDIT PER PROJECT

    # "checkout" | "elements"
    BILLING_MODE: str = "checkout"                   # EDIT PER PROJECT

    # ── Email ────────────────────────────────────────────────────────
    RESEND_API_KEY: str = "re_placeholder"           # EDIT PER PROJECT
    EMAIL_FROM: str = "noreply@example.com"          # EDIT PER PROJECT

    # ── Feature flags ────────────────────────────────────────────────
    # "modal" | "redirect"
    PAYWALL_MODE: str = "modal"
    ENABLE_GUEST_SESSIONS: bool = True
    GUEST_NUDGE_AFTER: int = 3

    # ── Rate limiting ────────────────────────────────────────────────
    RATE_LIMIT_WINDOW_SECONDS: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
