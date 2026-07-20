"""Model Router (Phase 4).

Alur:
    User -> Intent Detection -> Prompt -> Model Router -> GPT / Claude

Kalau user MEMILIH model sendiri di dropdown, pilihan itu MENANG.
Kalau model kosong / "auto", router memilihkan model terbaik per mode,
misalnya: Coding -> Claude, Marketing -> GPT.
"""
from ...core.config import settings
from .constants import ALL_MODELS, ANTHROPIC_MODELS, DEFAULT_MODEL, OPENAI_MODELS

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
    """Tentukan model final berdasarkan pilihan user, mode, dan API key aktif.

    - Pilihan eksplisit user tetap diprioritaskan bila provider-nya aktif.
    - Bila provider pilihan tidak aktif, jatuhkan ke provider lain yang tersedia.
    - OpenAI-only maupun Anthropic-only sama-sama didukung.
    """
    chosen = normalize_model(requested_model)
    if chosen is None:
        chosen = MODE_MODEL_MAP.get(mode) or settings.ANTHROPIC_MODEL or DEFAULT_MODEL

    has_openai = bool(settings.OPENAI_API_KEY)
    has_anthropic = bool(settings.ANTHROPIC_API_KEY)

    if chosen in OPENAI_MODELS and not has_openai:
        if has_anthropic:
            chosen = settings.ANTHROPIC_MODEL or DEFAULT_MODEL
    elif chosen in ANTHROPIC_MODELS and not has_anthropic:
        if has_openai:
            preferred_openai = getattr(settings, "PROFILING_OPENAI_MODEL", "")
            chosen = preferred_openai if preferred_openai in OPENAI_MODELS else "gpt-5.6-terra"

    if chosen not in ALL_MODELS:
        if has_openai:
            chosen = "gpt-5.6-terra"
        else:
            chosen = DEFAULT_MODEL
    return chosen


def is_openai(model: str) -> bool:
    return model in OPENAI_MODELS
