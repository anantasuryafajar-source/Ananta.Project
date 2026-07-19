"""Model Router (Phase 4).

Alur:
    User -> Intent Detection -> Prompt -> Model Router -> GPT / Claude

Kalau user MEMILIH model sendiri di dropdown, pilihan itu MENANG.
Kalau model kosong / "auto", router memilihkan model terbaik per mode,
misalnya: Coding -> Claude, Marketing -> GPT.
"""
from ...core.config import settings
from .constants import ALL_MODELS, DEFAULT_MODEL, OPENAI_MODELS

# Peta mode -> model pilihan router (mode yang tak terdaftar pakai DEFAULT_MODEL).
MODE_MODEL_MAP: dict[str, str] = {
    "coding": "claude-sonnet-5",          # coding -> Claude
    "research": "claude-sonnet-5",        # riset butuh reasoning + web_search Anthropic
    "profile": "claude-sonnet-5",
    "finance": "claude-sonnet-5",         # analisa data + tool use
    "legal": "claude-sonnet-5",
    "medical": "claude-sonnet-5",
    "marketing": "gpt-5.6-terra",         # marketing -> GPT
    "seo": "gpt-5.6-terra",
    "writer": "gpt-5.6-terra",
    "business": "claude-sonnet-5",
    "general": DEFAULT_MODEL,
}


def normalize_model(model: str | None) -> str | None:
    """Model valid dari input user, atau None bila kosong/'auto'/tak dikenal."""
    if not model or model == "auto":
        return None
    return model if model in ALL_MODELS else None


def route_model(mode: str, requested_model: str | None) -> str:
    """Tentukan model final.

    1. Pilihan eksplisit user menang.
    2. Kalau tidak ada, pakai peta mode->model.
    3. Kalau model hasil router adalah GPT tapi OPENAI_API_KEY kosong,
       jatuhkan ke model Claude default supaya fitur tetap jalan.
    """
    chosen = normalize_model(requested_model)
    if chosen is None:
        chosen = MODE_MODEL_MAP.get(mode) or settings.ANTHROPIC_MODEL or DEFAULT_MODEL
    if chosen in OPENAI_MODELS and not settings.OPENAI_API_KEY:
        chosen = settings.ANTHROPIC_MODEL or DEFAULT_MODEL
    if chosen not in ALL_MODELS:
        chosen = DEFAULT_MODEL
    return chosen


def is_openai(model: str) -> bool:
    return model in OPENAI_MODELS
