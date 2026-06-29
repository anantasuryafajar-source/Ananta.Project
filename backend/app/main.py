from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .routers import (
    auth, contacts, products, accounts, invoices, dashboard,
    purchases, payments, reports,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tempat init resource (redis pool, dll). DB pool dibuat lazy di engine.
    yield


app = FastAPI(
    title="Ananta API",
    version="0.1.0",
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


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "env": settings.ENV}
