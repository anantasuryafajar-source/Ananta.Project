"""Prompt Registry (Phase 1 & 2).

Satu tempat untuk semua system prompt per-mode. Pemakaian:

    from ..prompts import get_system_prompt, MODES
    system = get_system_prompt("marketing")

Prompt final = BASE_PROMPT (identitas + akses data ASF) + prompt mode.
"""
from .base import BASE_PROMPT
from .general import GENERAL_PROMPT
from .marketing import MARKETING_PROMPT
from .seo import SEO_PROMPT
from .coding import CODING_PROMPT
from .business import BUSINESS_PROMPT
from .finance import FINANCE_PROMPT
from .medical import MEDICAL_PROMPT
from .legal import LEGAL_PROMPT
from .writer import WRITER_PROMPT
from .research import RESEARCH_PROMPT
from .profile import PROFILE_PROMPT

# Registry: mode -> prompt tambahan (ditempel setelah BASE_PROMPT).
PROMPTS: dict[str, str] = {
    "general": GENERAL_PROMPT,
    "marketing": MARKETING_PROMPT,
    "seo": SEO_PROMPT,
    "coding": CODING_PROMPT,
    "business": BUSINESS_PROMPT,
    "finance": FINANCE_PROMPT,
    "medical": MEDICAL_PROMPT,
    "legal": LEGAL_PROMPT,
    "writer": WRITER_PROMPT,
    "research": RESEARCH_PROMPT,
    "profile": PROFILE_PROMPT,
}

DEFAULT_MODE = "general"

# Label untuk dropdown di frontend (GET /ai/config).
MODE_LABELS: dict[str, str] = {
    "general": "General",
    "marketing": "Marketing",
    "seo": "SEO",
    "coding": "Coding",
    "business": "Business",
    "finance": "Finance",
    "medical": "Medical",
    "legal": "Legal",
    "writer": "Writer",
    "research": "Research",
    "profile": "Profile Research",
}

MODES = list(PROMPTS.keys())


def normalize_mode(mode: str | None) -> str | None:
    """Kembalikan mode valid, atau None bila kosong/'auto' (=> intent detection)."""
    if not mode or mode == "auto":
        return None
    m = mode.strip().lower()
    return m if m in PROMPTS else None


def get_system_prompt(mode: str | None) -> str:
    """System prompt final untuk sebuah mode (base + mode)."""
    m = normalize_mode(mode) or DEFAULT_MODE
    extra = PROMPTS.get(m, "")
    return f"{BASE_PROMPT}\n\n{extra}".strip() if extra else BASE_PROMPT
