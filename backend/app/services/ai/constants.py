"""Konstanta bersama untuk paket AI: model, effort, endpoint."""

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

MAX_TOOL_ROUNDS = 5
HTTP_TIMEOUT = 120

# Model Anthropic yang diizinkan (allowlist). Label untuk info.
ANTHROPIC_MODELS = {
    "claude-sonnet-5": "Sonnet (seimbang)",
    "claude-opus-4-8": "Opus (paling cerdas)",
    "claude-haiku-4-5-20251001": "Haiku (paling cepat)",
}
DEFAULT_MODEL = "claude-sonnet-5"

# Model murah/cepat khusus intent detection (klasifikasi 1 kata).
INTENT_MODEL = "claude-haiku-4-5-20251001"

# Model OpenAI (ChatGPT).
OPENAI_MODELS = {
    "gpt-5.6-sol": "GPT-5.6 Sol (paling pintar)",
    "gpt-5.6-terra": "GPT-5.6 Terra (seimbang)",
    "gpt-5.6-luna": "GPT-5.6 Luna (cepat/murah)",
}

# Gabungan untuk dropdown & validasi.
ALL_MODELS = {**ANTHROPIC_MODELS, **OPENAI_MODELS}

# Effort -> anggaran token berpikir (extended thinking). Low = tanpa thinking.
EFFORT_BUDGET = {"low": 0, "medium": 4000, "high": 12000}
DEFAULT_EFFORT = "medium"

# Tool riset web bawaan Anthropic (dieksekusi di sisi server Anthropic).
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
