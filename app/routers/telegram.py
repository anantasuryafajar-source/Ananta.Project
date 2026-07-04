"""Endpoint webhook Telegram.

Di-mount TANPA prefix /api/v1. Telegram POST ke {BACKEND_PUBLIC_URL}/telegram/webhook
dengan header rahasia yang kita verifikasi.
"""
from fastapi import APIRouter, Header, HTTPException, Request

from ..bot.application import get_application
from ..core.config import settings

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    app_ = get_application()
    if app_ is None:
        raise HTTPException(status_code=503, detail="Bot Telegram tidak aktif.")

    if settings.TELEGRAM_WEBHOOK_SECRET and (
        x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="Secret token tidak cocok.")

    from telegram import Update

    data = await request.json()
    update = Update.de_json(data, app_.bot)
    await app_.process_update(update)
    return {"ok": True}
