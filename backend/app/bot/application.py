"""Siklus hidup Application python-telegram-bot, disatukan ke FastAPI.

Import telegram dijaga (guarded): bila paket belum terpasang atau token kosong,
bot dimatikan total dan API akuntansi tetap berjalan normal.
"""
import logging

from ..core.config import settings

log = logging.getLogger("ananta.bot")

try:
    from telegram.ext import Application

    _PTB_AVAILABLE = True
except Exception:  # pragma: no cover
    _PTB_AVAILABLE = False

_application = None


def get_application():
    """Application yang sudah start, atau None bila bot nonaktif."""
    return _application


def _build():
    from .handlers import register

    app_ = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).updater(None).build()
    register(app_)
    return app_


async def startup_bot() -> None:
    global _application
    if not _PTB_AVAILABLE or not settings.TELEGRAM_BOT_TOKEN:
        log.info("Bot Telegram nonaktif (paket/token tidak ada).")
        return

    app_ = _build()
    await app_.initialize()
    await app_.start()
    _application = app_

    # Set webhook (best-effort; kegagalan tidak menghentikan API).
    try:
        if settings.BACKEND_PUBLIC_URL and settings.TELEGRAM_WEBHOOK_SECRET:
            url = settings.BACKEND_PUBLIC_URL.rstrip("/") + "/telegram/webhook"
            await app_.bot.set_webhook(
                url=url,
                secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                allowed_updates=["message"],
            )
            log.info("Webhook Telegram diset ke %s", url)
    except Exception as e:  # pragma: no cover
        log.warning("Gagal set webhook Telegram: %s", e)


async def shutdown_bot() -> None:
    global _application
    if _application is not None:
        await _application.stop()
        await _application.shutdown()
        _application = None
