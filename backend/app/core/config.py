from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://ananta:ananta_dev_pw@localhost:5432/ananta"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 7

    SEED_ADMIN_EMAIL: str = "admin@ananta.local"
    SEED_ADMIN_PASSWORD: str = "admin12345"
    SEED_COMPANY_NAME: str = "Bisnisku"

    # Email (Resend) untuk reset kata sandi
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@anantaasf.com"
    APP_URL: str = "https://anantaasf.com"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Bot Telegram (langkah 1) ---
    # Token dari BotFather. Kalau kosong, bot dimatikan total (API tetap jalan).
    TELEGRAM_BOT_TOKEN: str = ""
    # Secret acak untuk memverifikasi webhook benar-benar dari Telegram.
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # URL publik backend ini di Railway, mis. https://ananta-api-production-e77c.up.railway.app
    BACKEND_PUBLIC_URL: str = ""

    # --- Asisten AI web ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    # Agent OpenAI (ChatGPT). Kosong = opsi GPT dan PROFILING 2.0 nonaktif.
    OPENAI_API_KEY: str = ""

    # --- PROFILING 2.0 via slash command /profiling ---
    PROFILING_OPENAI_MODEL: str = "gpt-5.6-terra"
    PROFILING_OPENAI_TIMEOUT_SECONDS: int = 300
    PROFILING_RESEARCH_MAX_OUTPUT_TOKENS: int = 14000
    PROFILING_SYNTHESIS_MAX_OUTPUT_TOKENS: int = 18000
    PROFILING_BLOCKED_DOMAINS: str = "reddit.com,quora.com,wikipedia.org"

    # Chat ID Telegram owner untuk bootstrap penautan pertama (sementara).
    TELEGRAM_OWNER_CHAT_ID: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
