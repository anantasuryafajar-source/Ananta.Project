# Asisten AI — tambah agent ChatGPT (OpenAI) di dropdown

Menambah pilihan model GPT di dropdown yang SAMA (campur Claude + GPT). Backend
memilih jalur (Anthropic vs OpenAI) otomatis berdasarkan model yang dipilih.

## Model GPT yang ditawarkan (per Juli 2026)
- gpt-5.6-sol   : GPT-5.6 Sol (paling pintar)   ~$5/$30 per 1J token
- gpt-5.6-terra : GPT-5.6 Terra (seimbang)      ~$2.50/$15
- gpt-5.6-luna  : GPT-5.6 Luna (cepat/murah)    ~$1/$6
(Sumber ID model: OpenAI, dicek 12 Juli 2026. Bila OpenAI mengubahnya, edit
OPENAI_MODELS di ai_assistant.py.)

## File berubah (backend saja; frontend TIDAK berubah)
- app/services/ai_assistant.py — jalur OpenAI (function calling) + daftar model
  gabungan (ALL_MODELS) + routing di answer()
- app/routers/ai_chat.py — endpoint /ai/config kirim daftar model gabungan
- app/core/config.py — OPENAI_API_KEY

Dropdown di web terisi otomatis dari /ai/config, jadi frontend tak perlu diubah.

Tidak ada migrasi baru. Dependency: pakai httpx yang sudah ada.

## Yang kamu siapkan
1. Akun OpenAI + API key di platform.openai.com -> API keys (sk-...).
2. Isi billing di sana (terpisah dari Anthropic).
3. Railway -> service ananta-api -> Variables -> tambah OPENAI_API_KEY = sk-...
   (langsung dari OpenAI ke Railway; jangan lewat chat/GitHub).

## Deploy (backend -> Railway)
```powershell
git add backend/app/services/ai_assistant.py backend/app/routers/ai_chat.py backend/app/core/config.py
git commit -m "ai: tambah agent ChatGPT (OpenAI) di dropdown model"
git push
```
Tonton Railway "Healthcheck succeeded". Lalu di web -> Asisten AI, dropdown model
kini berisi Claude + GPT. Pilih GPT untuk pakai ChatGPT.

## Batasan versi pertama (jujur)
- Agent GPT: chat + 11 alat baca data ASF (laba rugi, arus kas, dst) - JALAN.
- Riset web & upload file: untuk sekarang HANYA di model Claude (mekanisme
  OpenAI beda; menyusul di paket berikutnya).
- Dropdown Effort: untuk sekarang memengaruhi Claude saja; GPT diabaikan (aman).
- Bila OPENAI_API_KEY kosong: memilih GPT membalas "Agent ChatGPT belum aktif";
  Claude & fitur lain tetap normal.
- Belum diuji ke API OpenAI sungguhan di lingkungan build (jaringan mati). Yang
  dipastikan: compile, routing benar, tools dikonversi ke format OpenAI, error
  ditampilkan informatif. Bila GPT error saat dipakai, pesan galat akan memandu
  (biasanya soal key/billing/model).

## Catatan biaya
Sekarang kamu punya DUA billing terpisah: Anthropic (Claude) & OpenAI (GPT).
Tiap agent menagih ke penyedianya masing-masing.
