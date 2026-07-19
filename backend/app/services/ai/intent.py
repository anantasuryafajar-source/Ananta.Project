"""Intent Detection (Phase 3).

Kalau user lupa/tidak memilih mode, AI mengklasifikasi sendiri pesan user
ke salah satu mode di prompt registry.

Contoh:
    "Buat caption"     -> marketing
    "Analisa laporan"  -> finance
    "Debug Python"     -> coding
    "SEO artikel"      -> seo

Strategi 2 lapis:
1. Heuristik kata kunci (0 biaya, 0 latensi) untuk kasus yang sangat jelas.
2. Klasifikasi via model murah (Haiku) bila heuristik tidak yakin.
Selalu jatuh ke "general" bila keduanya gagal.
"""
import logging
import re

import httpx

from ...core.config import settings
from ...prompts import DEFAULT_MODE, MODES
from .constants import ANTHROPIC_URL, INTENT_MODEL

log = logging.getLogger("ananta.ai.intent")

# Lapis 1: kata kunci yang sangat jelas per mode (dicek pada pesan lowercase).
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("coding", ("debug", "error", "bug", "python", "javascript", "typescript",
                "sql", "kode", "coding", "script", "api endpoint", "traceback",
                "refactor", "fungsi ", "function ")),
    ("seo", ("seo", "keyword", "serp", "meta description", "backlink",
             "search engine", "ranking google")),
    ("marketing", ("caption", "iklan", "ads", "copywriting", "tiktok",
                   "instagram", "landing page", "campaign", "kampanye",
                   "content calendar", "promosi")),
    ("finance", ("laba rugi", "neraca", "arus kas", "cashflow", "piutang",
                 "margin", "gpm", "komisi", "pajak", "ppn", "omzet",
                 "laporan keuangan", "keuangan")),
    ("legal", ("hukum", "legal", "kontrak", "perjanjian", "uu ", "undang-undang",
               "izin usaha", "nppbkc", "pasal")),
    ("medical", ("gejala", "penyakit", "obat", "dokter", "kesehatan",
                 "diagnosa", "medis")),
    ("writer", ("tulis artikel", "tuliskan", "email untuk", "proposal",
                "press release", "cerpen", "puisi", "edit tulisan")),
    ("business", ("swot", "business plan", "rencana bisnis", "strategi bisnis",
                  "model bisnis", "ekspansi", "pricing")),
    ("research", ("riset mendalam", "deep research", "riset pasar",
                  "bandingkan kompetitor", "studi banding")),
]

_WORD_RE = re.compile(r"[a-z]+")


def detect_by_keywords(message: str) -> str | None:
    """Lapis 1: heuristik kata kunci. None bila tidak yakin."""
    text = f" {message.lower()} "
    for mode, keys in _KEYWORDS:
        for k in keys:
            if k in text:
                return mode
    return None


async def detect_by_model(message: str) -> str | None:
    """Lapis 2: klasifikasi via Haiku (murah & cepat). None bila gagal."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    system = (
        "Klasifikasikan pesan user ke SATU kategori berikut: "
        + ", ".join(MODES)
        + ". Balas HANYA dengan satu kata nama kategori (huruf kecil), tanpa penjelasan. "
        "Kalau ragu atau pesan bersifat umum/sapaan, jawab: general."
    )
    payload = {
        "model": INTENT_MODEL,
        "max_tokens": 10,
        "system": system,
        "messages": [{"role": "user", "content": message[:1000]}],
    }
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        texts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        word = (_WORD_RE.search(" ".join(texts).lower()) or [None])
        word = word.group(0) if hasattr(word, "group") else None
        return word if word in MODES else None
    except Exception as e:  # pragma: no cover
        log.warning("intent detection gagal: %s", e)
        return None


async def detect_mode(message: str) -> str:
    """Deteksi mode untuk sebuah pesan. Selalu mengembalikan mode valid."""
    mode = detect_by_keywords(message)
    if mode:
        return mode
    mode = await detect_by_model(message)
    return mode or DEFAULT_MODE
