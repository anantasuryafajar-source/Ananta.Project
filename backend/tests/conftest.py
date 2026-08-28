import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import Base


@pytest_asyncio.fixture
async def db():
    # SQLite in-memory async untuk uji unit logika akuntansi (cepat, tanpa Postgres).
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # SQLite MEMATIKAN foreign key secara default; Postgres (produksi) TIDAK.
    # Tanpa baris ini, bug seperti "hapus faktur ditolak karena masih
    # direferensi invoice_terms" lolos di tes dan baru meledak di produksi.
    # Nyalakan supaya tes menegakkan FK sekuat produksi.
    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()
