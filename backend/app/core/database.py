"""Engine database — kompatibel Supabase (Supavisor) maupun Postgres langsung.

Menormalkan DATABASE_URL secara otomatis:
- memaksa driver asyncpg,
- membuang query yang TIDAK dimengerti asyncpg (sslmode, pgbouncer, channel_binding)
  yang sering ikut tercopy dari connection string Supabase,
- bila memakai TRANSACTION pooler Supabase (port 6543), mematikan prepared statement
  (NullPool + statement_cache_size=0 + nama statement unik) supaya tidak kena
  DuplicatePreparedStatementError dari Supavisor/PgBouncer.

Rekomendasi untuk ASF: pakai SESSION pooler (port 5432, host *.pooler.supabase.com)
— IPv4-friendly (Railway/Render IPv4-only) dan mendukung prepared statement.
"""
from collections.abc import AsyncGenerator
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import uuid4
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool
from .config import settings

_DROP_QUERY = {"sslmode", "pgbouncer", "channel_binding", "options"}


def _normalize(url: str) -> tuple[str, bool]:
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _DROP_QUERY]
    is_tx_pooler = parts.port == 6543
    clean = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return clean, is_tx_pooler


_url, _tx_pooler = _normalize(settings.DATABASE_URL)

if _tx_pooler:
    # Supabase Transaction pooler (6543): prepared statement TIDAK didukung.
    engine = create_async_engine(
        _url,
        future=True,
        poolclass=NullPool,  # biarkan Supavisor yang mengelola koneksi
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
            "server_settings": {"jit": "off"},
            "timeout": 10,  # gagal cepat bila DB tak terjangkau
        },
    )
else:
    # Direct / Session pooler (5432): pool biasa aman dipakai.
    engine = create_async_engine(
        _url,
        future=True,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args={"timeout": 10},  # gagal cepat bila DB tak terjangkau
    )

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
