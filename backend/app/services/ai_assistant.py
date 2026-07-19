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
from . import reports_ext

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

# --- Agent OpenAI (ChatGPT) ---
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS = {
    "gpt-5.6-sol": "GPT-5.6 Sol (paling pintar)",
    "gpt-5.6-terra": "GPT-5.6 Terra (seimbang)",
    "gpt-5.6-luna": "GPT-5.6 Luna (cepat/murah)",
}
# Daftar gabungan untuk dropdown & validasi.
ALL_MODELS = {**ALLOWED_MODELS, **OPENAI_MODELS}

# Effort -> anggaran token berpikir (extended thinking). Low = tanpa thinking.
EFFORT_BUDGET = {"low": 0, "medium": 4000, "high": 12000}
DEFAULT_EFFORT = "medium"

# Tool riset web bawaan Anthropic (dieksekusi di sisi server Anthropic).
# Ada biaya per pencarian & akun API mungkin perlu mengaktifkannya.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}

SYSTEM_PROMPT = """Kamu adalah asisten AI di dalam aplikasi Ananta milik PT Ananta
Surya Fajar (ASF), distributor minuman beralkohol (Minol) di Indonesia. Kamu
membantu siapa pun yang bertanya — bebas topik apa pun, seperti asisten umum.

Kamu punya keahlian khusus & AKSES DATA ke keuangan ASF lewat tool: laba rugi,
neraca, piutang (+ vs limit kredit), nilai stok, arus kas bulanan, performa
penjualan per sales (Lempar/Collect), margin kotor (GPM), komisi sales, tren
kuartalan, dan ringkasan pajak. Gunakan tool yang tepat setiap pertanyaannya
menyangkut kondisi keuangan/bisnis ASF, dan JANGAN mengarang angka.

Konteks industri yang kamu pahami bila relevan: regulasi NPPBKC; Golongan A
(<5%), B (5-20%), C (>20%); rantai dingin (cold chain); HoReCa vs Modern Retail;
"Omzet Lempar" (nilai faktur terbit) vs "Omzet Collect" (dana riil yang masuk).

Kamu juga bisa RISET WEB (tool web_search) untuk info pasar, industri, harga
komoditas, tren, kompetitor, dan regulasi. Serta bisa membaca FILE yang diunggah
pengguna (PDF/gambar) bila dilampirkan. Untuk riset web: BOLEH soal pasar/industri/
regulasi; DILARANG mengumpulkan/menyusun profil atau biodata pribadi seseorang.

Aturan:
- Untuk pertanyaan umum (di luar data ASF), jawab sewajarnya dari pengetahuanmu,
  ringkas dan membantu — sama seperti asisten AI umum.
- Untuk pertanyaan tentang keuangan/bisnis ASF, WAJIB pakai tool untuk angka riil;
  jangan menebak. Untuk data ASF kamu hanya bisa MEMBACA — kalau diminta
  mengubah/menghapus data, arahkan ke aplikasi Ananta.
- Jujur soal keterbatasan: kamu tidak punya akses internet/data eksternal real-time;
  untuk topik umum kamu menjawab dari pengetahuan, bukan data live.
- Default berbahasa Indonesia; ikuti bahasa penanya bila berbeda."""


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


def normalize_model(model: str | None) -> str:
    return model if model in ALL_MODELS else (settings.ANTHROPIC_MODEL or DEFAULT_MODEL)


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
        "tools": TOOLS + [WEB_SEARCH_TOOL],
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


def _openai_tools():
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


async def _post_openai(payload: dict, headers: dict) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OPENAI_URL, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def _answer_openai(history: list[dict], company_id: str, model: str) -> str:
    """Jalur agent ChatGPT: chat + alat baca data ASF (function calling)."""
    if not settings.OPENAI_API_KEY:
        return "Agent ChatGPT belum aktif (OPENAI_API_KEY belum diset di Railway)."

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "content-type": "application/json",
    }
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    tools = _openai_tools()
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "max_completion_tokens": 2000,
                # GPT-5.x: tools + reasoning tak didukung di chat/completions,
                # kecuali reasoning_effort='none'. Set none agar function tools jalan.
                "reasoning_effort": "none",
            }
            resp = await _post_openai(payload, headers)
            choice = (resp.get("choices") or [{}])[0].get("message", {})
            tool_calls = choice.get("tool_calls")
            if not tool_calls:
                return (choice.get("content") or "").strip() or "(tidak ada jawaban)"
            # rekam pesan asisten (berisi tool_calls) lalu jalankan tiap tool
            messages.append(choice)
            for tc in tool_calls:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                out = await _run_tool(fn.get("name", ""), args, company_id)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.get("id"), "content": out}
                )
        return "Analisis terlalu panjang; coba persempit pertanyaannya."
    except httpx.HTTPStatusError as e:  # pragma: no cover
        detail = ""
        try:
            detail = (e.response.json().get("error", {}) or {}).get("message", "") or ""
        except Exception:
            detail = (e.response.text or "")[:300]
        status = e.response.status_code
        log.warning("OpenAI API %s: %s", status, detail)
        hint = ""
        if status in (401, 403):
            hint = " (cek OPENAI_API_KEY di Railway)"
        elif status == 429 or "quota" in detail.lower() or "billing" in detail.lower():
            hint = " (saldo/billing OpenAI belum cukup)"
        elif status == 404 and "model" in detail.lower():
            hint = " (nama model GPT tidak dikenal akunmu)"
        return f"Galat OpenAI {status}: {detail or 'tidak diketahui'}{hint}"
    except Exception as e:  # pragma: no cover
        log.warning("OpenAI gagal: %s", e)
        return "Maaf, terjadi kesalahan saat memanggil ChatGPT."


async def answer(history: list[dict], company_id: str, model=None, effort=None,
                 attachments=None) -> str:
    """history: [{role, content}] -> teks jawaban. attachments: blok konten (dokumen/gambar)."""
    if not settings.ANTHROPIC_API_KEY:
        return "Fitur AI belum aktif (ANTHROPIC_API_KEY belum diset di Railway)."

    model = normalize_model(model)
    effort = normalize_effort(effort)

    # Jika model OpenAI (ChatGPT), pakai jalur OpenAI (chat + alat baca data ASF).
    if model in OPENAI_MODELS:
        return await _answer_openai(history, company_id, model)

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    # Tempelkan lampiran (PDF/gambar) ke pesan user terakhir.
    if attachments and messages and messages[-1]["role"] == "user":
        blocks = list(attachments)
        blocks.append({"type": "text", "text": messages[-1]["content"]})
        messages[-1] = {"role": "user", "content": blocks}
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
