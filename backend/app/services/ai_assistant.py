"""SHIM kompatibilitas — isi asli sudah dipindah ke paket `services/ai/`.

File ini dipertahankan supaya import lama tetap jalan:

    from ..services import ai_assistant as ai
    ai.ALL_MODELS, ai.DEFAULT_MODEL, ai.answer(...)

Kode baru sebaiknya import langsung dari paket:

    from ..services import ai
"""
from .ai import (  # noqa: F401
    ALL_MODELS,
    ANTHROPIC_MODELS,
    DEFAULT_EFFORT,
    DEFAULT_MODE,
    DEFAULT_MODEL,
    EFFORT_BUDGET,
    MODE_LABELS,
    MODES,
    OPENAI_MODELS,
    AnswerResult,
    normalize_effort,
)
from .ai import answer as _answer

# Alias nama lama.
ALLOWED_MODELS = ANTHROPIC_MODELS


async def answer(history, company_id, model=None, effort=None, attachments=None,
                 mode=None):
    """Signature lama: mengembalikan STRING jawaban (bukan AnswerResult)."""
    result = await _answer(
        history, company_id=company_id, mode=mode, model=model,
        effort=effort, attachments=attachments,
    )
    return result.reply
