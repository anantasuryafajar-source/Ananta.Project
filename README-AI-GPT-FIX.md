# Perbaikan agent GPT — "reasoning_effort not supported"

Galat: "Function tools with reasoning_effort are not supported for gpt-5.6-terra
in /v1/chat/completions ... set reasoning_effort to 'none'."

Sebab: GPT-5.6 (model reasoning) tak bisa memakai function tools + reasoning di
endpoint chat/completions kecuali reasoning_effort='none'.

Perbaikan: kirim "reasoning_effort": "none" pada payload OpenAI. Alat baca data
ASF (function tools) kini jalan.

## File berubah
- backend/app/services/ai_assistant.py (satu baris payload OpenAI)

## Deploy
```powershell
git add backend/app/services/ai_assistant.py
git commit -m "fix: GPT-5.6 reasoning_effort=none agar function tools jalan"
git push
```
Tonton Railway "Healthcheck succeeded", lalu coba lagi pilih GPT & tanya.

## Catatan
- GPT menjawab tanpa reasoning panjang (cepat, cukup untuk asisten bisnis + data).
- Bila nanti mau reasoning penuh di GPT: perlu pindah ke endpoint /v1/responses
  (paket tersendiri, lebih besar).
- Model Claude tidak terpengaruh.
