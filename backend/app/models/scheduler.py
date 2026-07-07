"""Tabel penjaga idempotensi scheduler (insight terjadwal).

Karena API jalan >1 worker, tiap job terjadwal 'mengklaim' satu baris
UNIQUE(job, run_key) sebelum berjalan — hanya satu worker yang menang & benar-benar
mengeksekusi. Mencegah laporan terkirim dobel.
"""
from datetime import datetime
from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin


class SchedulerRun(Base, PKMixin):
    __tablename__ = "scheduler_runs"
    job: Mapped[str] = mapped_column(String(60), index=True)
    run_key: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint("job", "run_key", name="uq_scheduler_job_key"),
    )
