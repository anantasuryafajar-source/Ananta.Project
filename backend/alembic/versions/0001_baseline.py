"""Baseline skema — seluruh tabel dibuat dari model SQLAlchemy.

Sebelum revisi ini, skema dibuat oleh `Base.metadata.create_all()` di dalam seed,
dan seed melewati seluruh prosesnya bila company sudah ada. Akibatnya model baru
tidak pernah membuat tabelnya di database yang sudah terisi — itu sebabnya dulu ada
SQL manual di `backend/migrations/*.sql` (kini sudah tercakup di sini).

Mulai revisi ini, skema dikelola Alembic: `alembic upgrade head` dijalankan
`entrypoint.sh` sebelum seed. Perubahan model BERIKUTNYA wajib punya revisi sendiri
(`alembic revision --autogenerate -m "..."`), jangan mengandalkan seed.

Revision ID: 0001_baseline
Revises: None
"""
from alembic import op

from app.models import Base

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst=True membuat revisi ini aman dijalankan pada database yang
    # tabelnya sudah dibuat create_all() sebelum Alembic dipakai.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
