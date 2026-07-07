"""Insight terjadwal (Bagian 4 spec).

Versi awal: satu snapshot harian dikirim ke chat OWNER pukul 08:00 WIB.
Aman untuk >1 worker lewat pengaman idempotensi (tabel scheduler_runs).
Kiriman per-eksekutif menyusul saat akun mereka tertaut.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.config import settings
from ..core.database import SessionLocal
from ..models import Role, SchedulerRun, User, UserRole
from ..services import reports_ext
from .application import get_application

log = logging.getLogger("ananta.insight")

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    _APS_AVAILABLE = True
except Exception:  # pragma: no cover
    _APS_AVAILABLE = False

_scheduler = None
WIB = timezone(timedelta(hours=7))


def _rp(v) -> str:
    try:
        n = int(Decimal(str(v)))
    except Exception:
        return f"Rp{v}"
    return "Rp" + f"{n:,}".replace(",", ".")


async def _owner_company_and_chat():
    """(company_id, owner_chat_id) untuk kiriman uji ke owner. (None, None) bila tak ada."""
    chat = str(settings.TELEGRAM_OWNER_CHAT_ID or "").strip()
    if not chat:
        return None, None
    async with SessionLocal() as db:
        owner = (
            await db.execute(
                select(User)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.name == "owner")
            )
        ).scalars().first()
    if owner is None:
        return None, None
    try:
        return owner.company_id, int(chat)
    except ValueError:
        return None, None


async def _due_bills(db, company_id: str, today):
    """Tagihan supplier belum lunas yang jatuh tempo <= 3 hari (termasuk lewat tempo)."""
    from ..models import Bill, Contact

    rows = (
        await db.execute(
            select(Bill.number, Contact.name, Bill.due_date, Bill.total, Bill.paid_total)
            .join(Contact, Contact.id == Bill.contact_id, isouter=True)
            .where(
                Bill.company_id == company_id,
                Bill.due_date.is_not(None),
                Bill.due_date <= today + timedelta(days=3),
                Bill.status.not_in(["draft", "void"]),
            )
        )
    ).all()
    out = []
    for number, name, dd, total, paid in rows:
        rem = Decimal(str(total or 0)) - Decimal(str(paid or 0))
        if rem > 0:
            out.append((dd, number, name or "-", rem))
    out.sort(key=lambda x: x[0])
    return out


async def build_daily_snapshot(company_id: str) -> str:
    today = datetime.now(WIB).date()
    async with SessionLocal() as db:
        cf = await reports_ext.cashflow(
            db, company_id, start=today - timedelta(days=1), end=today
        )
        kpi = await reports_ext.sales_kpi(
            db, company_id, start=today.replace(day=1), end=today
        )
        due = await _due_bills(db, company_id, today)
    items = kpi.get("items", [])
    lempar = sum((Decimal(i["omzet"]) for i in items), Decimal("0"))
    collect = sum((Decimal(i["paid"]) for i in items), Decimal("0"))

    text = (
        f"Snapshot Harian - {today.strftime('%d %b %Y')}\n\n"
        f"Kas masuk (24 jam) : {_rp(cf['total_in'])}\n"
        f"Kas keluar (24 jam): {_rp(cf['total_out'])}\n"
        f"Arus kas bersih    : {_rp(cf['net'])}\n\n"
        "Omzet bulan berjalan:\n"
        f"- Lempar  : {_rp(lempar)}\n"
        f"- Collect : {_rp(collect)}\n\n"
    )
    if due:
        text += "Tagihan supplier jatuh tempo (<=3 hari):\n"
        for dd, number, name, rem in due[:5]:
            text += f"- {dd.strftime('%d %b')} {number} {name} {_rp(rem)}\n"
        if len(due) > 5:
            text += f"...dan {len(due) - 5} lagi.\n"
        text += "\n"
    else:
        text += "Tagihan supplier jatuh tempo (<=3 hari): tidak ada.\n\n"

    text += "Ketik /report atau /omzet untuk detail."
    return text


async def _send(chat_id: int, text: str) -> None:
    app_ = get_application()
    if app_ is None:
        log.warning("Bot tak aktif; insight tak terkirim.")
        return
    await app_.bot.send_message(chat_id=chat_id, text=text)


async def _claim(job: str, run_key: str) -> bool:
    """True bila worker ini yang berhasil mengklaim job (hanya satu yang menang)."""
    async with SessionLocal() as db:
        db.add(SchedulerRun(job=job, run_key=run_key))
        try:
            await db.commit()
            return True
        except IntegrityError:
            await db.rollback()
            return False


async def run_daily_snapshot() -> None:
    """Dipanggil scheduler tiap 08:00 WIB. Idempoten antar-worker."""
    company_id, chat = await _owner_company_and_chat()
    if not company_id or not chat:
        return
    run_key = datetime.now(WIB).strftime("%Y-%m-%d")
    if not await _claim("daily_snapshot", run_key):
        return  # worker lain sudah mengirim hari ini
    try:
        text = await build_daily_snapshot(company_id)
        await _send(chat, text)
    except Exception as e:  # pragma: no cover
        log.warning("Snapshot harian gagal: %s", e)


async def send_test_snapshot(chat_id: int, company_id: str) -> None:
    """Untuk /insight_test — kirim segera, tanpa idempotensi."""
    text = await build_daily_snapshot(company_id)
    await _send(chat_id, text)


def start_scheduler() -> None:
    global _scheduler
    if not _APS_AVAILABLE or not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_OWNER_CHAT_ID:
        log.info("Scheduler insight nonaktif (paket/token/owner tidak ada).")
        return
    _scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
    _scheduler.add_job(
        run_daily_snapshot,
        "cron",
        hour=8,
        minute=0,
        id="daily_snapshot",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    log.info("Scheduler insight aktif (snapshot harian 08:00 WIB).")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
