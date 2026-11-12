"""IntentLock settings. One class, no insecure defaults for deployed modes.

Names follow the spec (`PAYPAL_ENV`, `GENAI_PROVIDER`, `DATABASE_URL`). A few older names are accepted as
aliases (`PAYPAL_MODE`, `AI_PROVIDER`, `POSTGRES_URL`, `JWT_SECRET`) so an existing deployment keeps working.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PAYPAL_BASE_URLS = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com",
}
MIN_SECRET_LEN = 32


class SettingsError(RuntimeError):
    """Raised at start-up when a required setting is missing or unsafe."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = Field("development", validation_alias=AliasChoices("APP_ENV"))
    frontend_url: str = Field("http://localhost:3000", validation_alias=AliasChoices("FRONTEND_URL"))
    database_url: str = Field("", validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL"))
    session_secret: str = Field("", validation_alias=AliasChoices("SESSION_SECRET", "JWT_SECRET"))
    receipt_signing_key: str = Field("", validation_alias=AliasChoices("RECEIPT_SIGNING_KEY"))

    paypal_env: str = Field("sandbox", validation_alias=AliasChoices("PAYPAL_ENV", "PAYPAL_MODE"))
    paypal_base_url: str = Field("", validation_alias=AliasChoices("PAYPAL_BASE_URL"))
    paypal_client_id: str = Field("", validation_alias=AliasChoices("PAYPAL_CLIENT_ID"))
    paypal_client_secret: str = Field("", validation_alias=AliasChoices("PAYPAL_CLIENT_SECRET"))
    paypal_webhook_id: str = Field("", validation_alias=AliasChoices("PAYPAL_WEBHOOK_ID"))
    paypal_merchant_id: str = Field("", validation_alias=AliasChoices("PAYPAL_MERCHANT_ID"))
    paypal_currency: str = Field("USD", validation_alias=AliasChoices("PAYPAL_CURRENCY"))

    genai_enabled: bool = Field(True, validation_alias=AliasChoices("GENAI_ENABLED"))
    genai_provider: str = Field("gemini", validation_alias=AliasChoices("GENAI_PROVIDER", "AI_PROVIDER"))
    genai_api_key: str = Field("", validation_alias=AliasChoices("GENAI_API_KEY"))
    genai_model: str = Field("gemini-3.1-flash-lite", validation_alias=AliasChoices("GENAI_MODEL"))
    genai_timeout_seconds: float = Field(15.0, validation_alias=AliasChoices("GENAI_TIMEOUT_SECONDS"))

    demo_tools: bool = Field(False, validation_alias=AliasChoices("DEMO_TOOLS"))
    featured_receipt: str = Field("", validation_alias=AliasChoices("FEATURED_RECEIPT"))
    quote_ttl_minutes: int = Field(30, ge=1, le=1440, validation_alias=AliasChoices("QUOTE_TTL_MINUTES"))
    frontend_build_dir: str = Field("frontend/build", validation_alias=AliasChoices("FRONTEND_BUILD_DIR"))

    # ── derived ───────────────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url.strip()
        if not url:
            return "sqlite:///./intentlock.db"
        # Name the installed driver explicitly: newer SQLAlchemy defaults "postgresql://" to psycopg 3, which is not installed.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg2://" + url[len(prefix) :]
        return url

    @property
    def database_kind(self) -> str:
        return "postgresql" if self.resolved_database_url.startswith("postgresql") else "sqlite"

    @property
    def resolved_paypal_base_url(self) -> str:
        return (self.paypal_base_url.strip() or PAYPAL_BASE_URLS.get(self.paypal_env.lower(), "")).rstrip("/")

    @property
    def resolved_session_secret(self) -> str:
        if self.session_secret:
            return self.session_secret
        # Development only: a per-install secret so sessions survive a restart without a setting.
        return hashlib.sha256(f"dev:{self.resolved_database_url}".encode()).hexdigest()

    @property
    def resolved_receipt_key(self) -> str:
        return self.receipt_signing_key or hashlib.sha256(f"receipt:{self.resolved_session_secret}".encode()).hexdigest()

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret and self.resolved_paypal_base_url)

    @property
    def ai_configured(self) -> bool:
        return bool(self.genai_enabled and self.genai_api_key and self.genai_provider)

    def problems(self) -> list[str]:
        """Settings that must be fixed before this instance may take payments."""
        out: list[str] = []
        if self.paypal_env.lower() not in PAYPAL_BASE_URLS:
            out.append("PAYPAL_ENV must be 'sandbox' or 'live'")
        if not self.paypal_configured:
            out.append("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are required")
        if self.is_production:
            if self.database_kind != "postgresql":
                out.append("DATABASE_URL must point to PostgreSQL when APP_ENV=production")
            if len(self.session_secret) < MIN_SECRET_LEN:
                out.append(f"SESSION_SECRET must be at least {MIN_SECRET_LEN} characters when APP_ENV=production")
            if not self.paypal_webhook_id:
                out.append("PAYPAL_WEBHOOK_ID is required when APP_ENV=production")
        return out

    def require_valid(self) -> None:
        problems = self.problems()
        if problems:
            raise SettingsError("IntentLock refuses to start: " + "; ".join(problems))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
