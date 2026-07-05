"""Inti Asisten AI web (Bagian 6, versi web).

TERPISAH dari bot Telegram. Claude menjawab pertanyaan analisis berbasis data
riil Ananta lewat tool READ-ONLY (hanya membaca laporan; tidak bisa menulis).

Dukungan:
- pilihan MODEL (Sonnet / Opus / Haiku)
- pilihan EFFORT (low / medium / high) -> dipetakan ke extended thinking Claude.
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from ..core.config import settings
from ..core.database import SessionLocal
from . import reports

log = logging.getLogger("ananta.ai")

API_URL = "https://api.anthropic.com/v1/messages"
MAX_TOOL_ROUNDS = 5

# Model yang diizinkan (allowlist). Label untuk info; frontend punya labelnya sendiri.
ALLOWED_MODELS = {
    "claude-sonnet-5": "Sonnet (seimbang)",
    "claude-opus-4-8": "Opus (paling cerdas)",
    "claude-haiku-4-5-20251001": "Haiku (paling cepat)",
}
DEFAULT_MODEL = "claude-sonnet-5"

# Effort -> anggaran token berpikir (extended thinking). Low = tanpa thinking.
EFFORT_BUDGET = {"low": 0, "medium": 4000, "high": 12000}
DEFAULT_EFFORT = "medium"

SYSTEM_PROMPT = """Kamu adalah analis keuangan untuk PT Ananta Surya Fajar (ASF),
distributor minuman beralkohol (Minol) di Indonesia. Jawab dalam Bahasa Indonesia,
ringkas, strategis, dan berbasis DATA RIIL dari tool yang tersedia.

Pengetahuan industri:
- Regulasi NPPBKC; pembatasan distribusi Golongan A (<5%), B (5-20%), C (>20%).
- Rantai dingin (cold chain) untuk produk tertentu.
- HoReCa (Hotel/Restoran/Kafe) vs Modern Retail.
- "Omzet Lempar" (nilai faktur terbit) vs "Omzet Collect" (dana riil yang masuk).

Aturan:
- SELALU panggil tool untuk mengambil angka; jangan mengarang data.
- Kamu hanya bisa MEMBACA data. Kalau diminta mengubah/menghapus data, jelaskan
  bahwa itu harus lewat aplikasi Ananta, bukan lewatmu.
- Kalau data tak cukup, katakan terus terang.
- Fokus ke insight yang bisa ditindak."""


def _today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=7)).date()


def _pdate(s, default: date) -> date:
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


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
]


async def _run_tool(name: str, args: dict, company_id: str) -> str:
    today = _today()
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
            else:
                return json.dumps({"error": f"tool tak dikenal: {name}"})
        return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:  # pragma: no cover
        log.warning("tool %s gagal: %s", name, e)
        return json.dumps({"error": str(e)})


def normalize_model(model: str | None) -> str:
    return model if model in ALLOWED_MODELS else (settings.ANTHROPIC_MODEL or DEFAULT_MODEL)


def normalize_effort(effort: str | None) -> str:
    return effort if effort in EFFORT_BUDGET else DEFAULT_EFFORT


async def _post(payload: dict, headers: dict) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(API_URL, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def _call_api(messages: list, model: str, effort: str) -> dict:
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    budget = EFFORT_BUDGET[effort]
    payload = {
        "model": model,
        "max_tokens": 1500 + budget,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": messages,
    }
    if budget > 0:
        payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
    try:
        return await _post(payload, headers)
    except httpx.HTTPStatusError as e:
        # Bila extended thinking ditolak (400), ulangi tanpa thinking.
        if e.response.status_code == 400 and "thinking" in payload:
            payload.pop("thinking", None)
            payload["max_tokens"] = 1500
            return await _post(payload, headers)
        raise


async def answer(history: list[dict], company_id: str, model=None, effort=None) -> str:
    """history: [{role, content}] -> teks jawaban."""
    if not settings.ANTHROPIC_API_KEY:
        return "Fitur AI belum aktif (ANTHROPIC_API_KEY belum diset di Railway)."

    model = normalize_model(model)
    effort = normalize_effort(effort)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await _call_api(messages, model, effort)
            content = resp.get("content", [])
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                return ("\n".join(t for t in texts if t)).strip() or "(tidak ada jawaban)"
            messages.append({"role": "assistant", "content": content})
            results = []
            for tu in tool_uses:
                out = await _run_tool(tu["name"], tu.get("input", {}), company_id)
                results.append(
                    {"type": "tool_result", "tool_use_id": tu["id"], "content": out}
                )
            messages.append({"role": "user", "content": results})
        return "Analisis terlalu panjang; coba persempit pertanyaannya."
    except httpx.HTTPStatusError as e:  # pragma: no cover
        detail = ""
        try:
            j = e.response.json()
            detail = (j.get("error", {}) or {}).get("message", "") or ""
        except Exception:
            detail = (e.response.text or "")[:300]
        status = e.response.status_code
        log.warning("API AI %s: %s", status, detail)
        hint = ""
        if status in (401, 403):
            hint = " (cek ANTHROPIC_API_KEY di Railway — mungkin salah/di-revoke)"
        elif status == 400 and "credit" in detail.lower():
            hint = " (saldo/billing API Anthropic belum cukup)"
        elif status == 404 and "model" in detail.lower():
            hint = " (nama model tidak dikenal akunmu — ganti model)"
        return f"Galat API {status}: {detail or 'tidak diketahui'}{hint}"
    except Exception as e:  # pragma: no cover
        log.warning("AI gagal: %s", e)
        return "Maaf, terjadi kesalahan saat menganalisis."
