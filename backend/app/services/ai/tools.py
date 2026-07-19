"""Definisi & eksekusi tool baca data ASF (READ-ONLY).

Dipakai baik oleh jalur Claude (format Anthropic) maupun ChatGPT
(dikonversi ke function calling lewat openai_tools()).
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone

from ...core.database import SessionLocal
from .. import reports
from .. import reports_ext

log = logging.getLogger("ananta.ai.tools")


def today_wib() -> date:
    """Tanggal hari ini WIB (UTC+7)."""
    return (datetime.now(timezone.utc) + timedelta(hours=7)).date()


def _pdate(s, default: date) -> date:
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


# Definisi tool dalam format Anthropic.
TOOLS = [
    {
        "name": "get_profit_loss",
        "description": "Laba rugi (pendapatan, HPP, beban, laba bersih) untuk rentang tanggal. Default: awal tahun s/d hari ini.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
        },
    },
    {
        "name": "get_balance_sheet",
        "description": "Neraca (aset, kewajiban, ekuitas) per satu tanggal. Default: hari ini.",
        "input_schema": {
            "type": "object",
            "properties": {"as_of_date": {"type": "string"}},
        },
    },
    {
        "name": "get_receivables",
        "description": "Umur piutang (AR aging) — siapa berutang berapa. Default: hari ini.",
        "input_schema": {
            "type": "object",
            "properties": {"as_of_date": {"type": "string"}},
        },
    },
    {
        "name": "get_stock_valuation",
        "description": "Nilai persediaan saat ini per produk.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_cashflow",
        "description": "Arus kas (masuk/keluar/bersih) per bulan untuk rentang tanggal. Default: awal tahun s/d hari ini.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
        },
    },
    {
        "name": "get_sales_kpi",
        "description": "Performa penjualan per sales: jumlah faktur, omzet (Lempar), terbayar (Collect), rasio collect. Default: bulan berjalan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
        },
    },
    {
        "name": "get_gross_margin",
        "description": "Margin kotor / Gross Profit Margin (penjualan, HPP, laba kotor, %). Default: awal tahun s/d hari ini.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
        },
    },
    {
        "name": "get_commission",
        "description": "Komisi sales untuk rentang tanggal (berdasarkan omzet terbayar). Default: bulan berjalan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "rate": {"type": "number", "description": "Tarif komisi (mis. 0.05 = 5%). Default 0.05."},
            },
        },
    },
    {
        "name": "get_quarterly_recap",
        "description": "Tren per kuartal: omzet & HPP. Untuk melihat pertumbuhan antar kuartal.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_ar_limit",
        "description": "Piutang tiap customer vs limit kredit mereka — siapa yang mendekati/melewati batas kredit.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_tax_summary",
        "description": "Ringkasan pajak (mis. PPN keluaran/masukan) untuk rentang tanggal. Default: bulan berjalan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
        },
    },
]


def openai_tools() -> list[dict]:
    """Konversi TOOLS (format Anthropic) ke format function-calling OpenAI."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


async def run_tool(name: str, args: dict, company_id: str) -> str:
    """Jalankan satu tool baca data ASF; hasil JSON string (atau {error})."""
    today = today_wib()
    try:
        async with SessionLocal() as db:
            if name == "get_profit_loss":
                start = _pdate(args.get("start_date"), date(today.year, 1, 1))
                end = _pdate(args.get("end_date"), today)
                data = await reports.profit_loss(db, company_id, start=start, end=end)
            elif name == "get_balance_sheet":
                data = await reports.balance_sheet(
                    db, company_id, as_of=_pdate(args.get("as_of_date"), today)
                )
            elif name == "get_receivables":
                data = await reports.ar_aging(
                    db, company_id, as_of=_pdate(args.get("as_of_date"), today)
                )
            elif name == "get_stock_valuation":
                data = await reports.stock_valuation(db, company_id)
            elif name == "get_cashflow":
                start = _pdate(args.get("start_date"), date(today.year, 1, 1))
                end = _pdate(args.get("end_date"), today)
                data = await reports_ext.cashflow(db, company_id, start=start, end=end)
            elif name == "get_sales_kpi":
                start = _pdate(args.get("start_date"), today.replace(day=1))
                end = _pdate(args.get("end_date"), today)
                data = await reports_ext.sales_kpi(db, company_id, start=start, end=end)
            elif name == "get_gross_margin":
                start = _pdate(args.get("start_date"), date(today.year, 1, 1))
                end = _pdate(args.get("end_date"), today)
                data = await reports_ext.gpm(db, company_id, start=start, end=end)
            elif name == "get_commission":
                start = _pdate(args.get("start_date"), today.replace(day=1))
                end = _pdate(args.get("end_date"), today)
                rate = args.get("rate")
                rate = float(rate) if isinstance(rate, (int, float)) else 0.05
                data = await reports_ext.commission(
                    db, company_id, start=start, end=end, rate=rate
                )
            elif name == "get_quarterly_recap":
                data = await reports_ext.quarterly_recap(db, company_id)
            elif name == "get_ar_limit":
                data = await reports_ext.ar_limit(db, company_id)
            elif name == "get_tax_summary":
                start = _pdate(args.get("start_date"), today.replace(day=1))
                end = _pdate(args.get("end_date"), today)
                data = await reports_ext.tax_summary(db, company_id, start=start, end=end)
            else:
                return json.dumps({"error": f"tool tak dikenal: {name}"})
        return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:  # pragma: no cover
        log.warning("tool %s gagal: %s", name, e)
        return json.dumps({"error": str(e)})
