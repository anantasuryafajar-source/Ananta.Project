"""Jalur Claude (Anthropic): chat + tool baca data ASF + web_search + lampiran."""
import logging

import httpx

from ...core.config import settings
from .constants import (
    ANTHROPIC_URL,
    EFFORT_BUDGET,
    HTTP_TIMEOUT,
    MAX_TOOL_ROUNDS,
    WEB_SEARCH_TOOL,
)
from .tools import TOOLS, run_tool

log = logging.getLogger("ananta.ai.anthropic")


async def _post(payload: dict, headers: dict) -> dict:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        r = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def _call_api(messages: list, system: str, model: str, effort: str) -> dict:
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    budget = EFFORT_BUDGET[effort]
    payload = {
        "model": model,
        "max_tokens": 1500 + budget,
        "system": system,
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


async def answer_anthropic(
    history: list[dict],
    system: str,
    company_id: str,
    model: str,
    effort: str,
    attachments: list | None = None,
) -> str:
    """Jalankan loop percakapan + tool untuk model Claude. Return teks jawaban."""
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    # Tempelkan lampiran (PDF/gambar) ke pesan user terakhir.
    if attachments and messages and messages[-1]["role"] == "user":
        blocks = list(attachments)
        blocks.append({"type": "text", "text": messages[-1]["content"]})
        messages[-1] = {"role": "user", "content": blocks}
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await _call_api(messages, system, model, effort)
            content = resp.get("content", [])
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                return ("\n".join(t for t in texts if t)).strip() or "(tidak ada jawaban)"
            messages.append({"role": "assistant", "content": content})
            results = []
            for tu in tool_uses:
                out = await run_tool(tu["name"], tu.get("input", {}), company_id)
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
