from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .routers import (
    auth, contacts, products, accounts, invoices, dashboard,
    purchases, payments, reports,
    # --- modul distribusi ASF ---
    warehouses, courier, orders, reports_ext, settings as settings_router, account,
    bulk_import, journals,
    # --- modul keuangan lanjutan ---
    investors, expenses,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Ananta API",
    version="0.6.0",
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


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "env": settings.ENV}
