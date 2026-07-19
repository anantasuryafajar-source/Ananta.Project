"""Jalur ChatGPT (OpenAI): chat + tool baca data ASF via function calling."""
import json
import logging

import httpx

from ...core.config import settings
from .constants import HTTP_TIMEOUT, MAX_TOOL_ROUNDS, OPENAI_URL
from .tools import openai_tools, run_tool

log = logging.getLogger("ananta.ai.openai")


async def _post(payload: dict, headers: dict) -> dict:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        r = await client.post(OPENAI_URL, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def answer_openai(
    history: list[dict],
    system: str,
    company_id: str,
    model: str,
) -> str:
    """Jalankan loop percakapan + function calling untuk model GPT."""
    if not settings.OPENAI_API_KEY:
        return "Agent ChatGPT belum aktif (OPENAI_API_KEY belum diset di Railway)."

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "content-type": "application/json",
    }
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    tools = openai_tools()
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
            resp = await _post(payload, headers)
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
                out = await run_tool(fn.get("name", ""), args, company_id)
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
