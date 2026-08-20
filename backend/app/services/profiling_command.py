"""Parser slash command PROFILING 2.0 untuk chat Ananta."""
from __future__ import annotations

import re

_PROFILE_COMMAND_RE = re.compile(
    r"^/(?P<command>profiling|profling)(?:\s+(?P<arguments>.*))?$",
    re.IGNORECASE | re.DOTALL,
)


def parse_profiling_command(text: str) -> tuple[bool, dict | None]:
    """Parse slash command; return ``(is_command, target_or_none)``.

    Format minimum:
        /profiling Nama Lengkap

    Format lengkap:
        /profiling Nama | Jabatan | Instansi | Wilayah | Periode
    """
    match = _PROFILE_COMMAND_RE.fullmatch((text or "").strip())
    if not match:
        return False, None

    raw = (match.group("arguments") or "").strip()
    if not raw:
        return True, None

    parts = [part.strip() for part in raw.split("|", 4)]
    parts += [""] * (5 - len(parts))
    name, known_position, institution, region, known_period = parts
    if not name:
        return True, None

    return True, {
        "name": name,
        "known_position": known_position or None,
        "institution": institution or None,
        "region": region or None,
        "known_period": known_period or None,
        "extra_context": None,
    }


def profiling_usage() -> str:
    return (
        "Gunakan perintah berikut:\n\n"
        "/profiling Nama Lengkap\n\n"
        "Contoh:\n"
        "/profiling Dedi Prasetyo\n\n"
        "Untuk membantu membedakan nama yang sama, konteks tambahan dapat ditulis "
        "dengan tanda |:\n"
        "/profiling Nama | Jabatan | Instansi | Wilayah | Periode\n\n"
        "Alias /profling juga diterima."
    )


def profiling_reply(result: dict) -> str:
    text = (result.get("document_text") or "").strip()
    reasons = result.get("review_reasons") or []
    if reasons:
        text += "\n\nSTATUS REVIEW\n"
        text += "Hasil ini masih perlu diperiksa manusia sebelum digunakan sebagai data final.\n"
        text += "\n".join(f"- {reason}" for reason in reasons)
    return text or "Profiling selesai, tetapi dokumen tidak berhasil dibentuk."
