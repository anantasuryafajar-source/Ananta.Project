from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .routers import (
    auth, contacts, products, accounts, invoices, dashboard,
    purchases, payments, reports,
    # --- modul distribusi ASF ---
    warehouses, courier, orders, reports_ext, settings as settings_router, account,
    bulk_import, journals, audit, reconcile,
    # --- modul keuangan lanjutan ---
    investors, expenses,
    # --- Bot Telegram (langkah 1) ---
    telegram as telegram_router,
    ai_chat,
)
import logging
from .bot.application import startup_bot, shutdown_bot

_bot_log = logging.getLogger("ananta.bot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bot Telegram bersifat OPSIONAL. Kegagalan apa pun di sini TIDAK boleh
    # membuat API akuntansi crash (healthcheck /health harus tetap lolos).
    try:
        await startup_bot()
    except Exception as e:  # pragma: no cover
        _bot_log.warning("Bot Telegram gagal start; API tetap jalan: %s", e)
    yield
    try:
        await shutdown_bot()
    except Exception:  # pragma: no cover
        pass


app = FastAPI(
    title="Ananta API",
    version="0.9.2",
    description="Sistem manajemen bisnis & akuntansi Ananta.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"

for r in (auth, contacts, products, accounts, invoices, dashboard,
          purchases, payments, reports):
    app.include_router(r.router, prefix=API)

app.include_router(warehouses.router, prefix=API)
app.include_router(warehouses.transfer_router, prefix=API)
app.include_router(courier.router, prefix=API)
app.include_router(orders.po_router, prefix=API)
app.include_router(orders.so_router, prefix=API)
app.include_router(reports_ext.router, prefix=API)
app.include_router(settings_router.router, prefix=API)
app.include_router(investors.router, prefix=API)
app.include_router(expenses.router, prefix=API)
app.include_router(expenses.loan_router, prefix=API)
app.include_router(account.router, prefix=API)
app.include_router(bulk_import.router, prefix=API)
app.include_router(journals.router, prefix=API)
app.include_router(audit.router, prefix=API)
app.include_router(reconcile.router, prefix=API)

# Bot Telegram: webhook di-mount TANPA prefix /api/v1 (Telegram POST ke URL bersih).
app.include_router(telegram_router.router)
app.include_router(ai_chat.router, prefix=API)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "env": settings.ENV}
