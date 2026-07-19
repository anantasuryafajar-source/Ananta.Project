"""Paket Asisten AI web — hasil refactor dari ai_assistant.py monolitik.

Alur (Phase 2-4):

    User
      ↓
    Intent Detection  (bila mode kosong/auto)          -> intent.py
      ↓
    Prompt            (PROMPTS[mode], base + mode)     -> app/prompts/
      ↓
    Model Router      (mode -> GPT / Claude)           -> router.py
      ↓
    GPT / Claude      (+ tool baca data ASF)           -> openai_client.py /
                                                          anthropic_client.py

Pemakaian dari router FastAPI:

    from ..services import ai
    result = await ai.answer(history, company_id=..., mode=..., model=..., ...)
    result.reply, result.mode, result.model
"""
import logging
from dataclasses import dataclass

from ...core.config import settings
from ...prompts import (
    DEFAULT_MODE,
    MODE_LABELS,
    MODES,
    get_system_prompt,
    normalize_mode,
)
from .anthropic_client import answer_anthropic
from .constants import (
    ALL_MODELS,
    ANTHROPIC_MODELS,
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    EFFORT_BUDGET,
    OPENAI_MODELS,
)
from .intent import detect_mode
from .openai_client import answer_openai
from .router import is_openai, route_model

log = logging.getLogger("ananta.ai")

__all__ = [
    "answer",
    "AnswerResult",
    "ALL_MODELS",
    "ANTHROPIC_MODELS",
    "OPENAI_MODELS",
    "DEFAULT_MODEL",
    "DEFAULT_EFFORT",
    "EFFORT_BUDGET",
    "MODES",
    "MODE_LABELS",
    "DEFAULT_MODE",
    "normalize_effort",
]


def normalize_effort(effort: str | None) -> str:
    return effort if effort in EFFORT_BUDGET else DEFAULT_EFFORT


@dataclass
class AnswerResult:
    reply: str
    mode: str          # mode final yang dipakai (hasil pilihan user / intent detection)
    model: str         # model final yang dipakai (hasil pilihan user / router)
    mode_detected: bool  # True bila mode hasil intent detection (bukan pilihan user)


async def answer(
    history: list[dict],
    company_id: str,
    mode: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    attachments: list | None = None,
) -> AnswerResult:
    """Jawab pesan terakhir di history.

    history: [{role, content}] — pesan terakhir harus role 'user'.
    mode: salah satu MODES, atau None/'auto' -> intent detection.
    model: id model, atau None/'auto' -> model router.
    """
    if not settings.ANTHROPIC_API_KEY:
        return AnswerResult(
            reply="Fitur AI belum aktif (ANTHROPIC_API_KEY belum diset di Railway).",
            mode=DEFAULT_MODE, model=DEFAULT_MODEL, mode_detected=False,
        )

    # 1) Mode: pilihan user, atau intent detection (Phase 3).
    final_mode = normalize_mode(mode)
    mode_detected = False
    if final_mode is None:
        last_user = next(
            (m["content"] for m in reversed(history)
             if m.get("role") == "user" and isinstance(m.get("content"), str)),
            "",
        )
        final_mode = await detect_mode(last_user)
        mode_detected = True

    # 2) Prompt: registry (Phase 1-2).
    system = get_system_prompt(final_mode)

    # 3) Model: pilihan user menang; kalau tidak, router per mode (Phase 4).
    final_model = route_model(final_mode, model)

    # 4) Eksekusi ke provider yang tepat.
    effort = normalize_effort(effort)
    if is_openai(final_model):
        # Catatan: lampiran PDF/gambar hanya didukung jalur Claude.
        reply = await answer_openai(history, system, company_id, final_model)
    else:
        reply = await answer_anthropic(
            history, system, company_id, final_model, effort, attachments
        )

    log.info("ai.answer mode=%s(auto=%s) model=%s", final_mode, mode_detected, final_model)
    return AnswerResult(reply=reply, mode=final_mode, model=final_model,
                        mode_detected=mode_detected)
