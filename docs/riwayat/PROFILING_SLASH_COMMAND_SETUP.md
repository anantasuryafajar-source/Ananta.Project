# Integrasi PROFILING 2.0 sebagai Slash Command

Patch ini menambahkan PROFILING 2.0 langsung ke halaman **Asisten AI** Ananta.
Tidak ada halaman `/profiling`, menu sidebar, model database, atau migrasi baru.
Hasil tersimpan menggunakan tabel percakapan AI yang sudah ada.

## Cara memakai

Input minimum:

```text
/profiling Nama Lengkap
```

Contoh:

```text
/profiling Dedi Prasetyo
```

Alias salah ketik juga diterima:

```text
/profling Dedi Prasetyo
```

Konteks opsional untuk membedakan orang bernama sama:

```text
/profiling Nama | Jabatan | Instansi | Wilayah | Periode
```

Contoh:

```text
/profiling Dedi Prasetyo | Wakapolri | Polri | Indonesia | 2025-sekarang
```

## File yang ditambahkan

```text
backend/app/services/profiling.py
backend/app/services/profiling_command.py
backend/tests/test_profiling_slash_command.py
```

## File yang diubah

```text
app/(app)/asisten/page.tsx
backend/app/core/config.py
backend/app/routers/ai_chat.py
backend/app/services/ai/__init__.py
backend/app/services/ai/router.py
backend/.env.example
```

`package.json`, sidebar, `main.py`, dan database tidak perlu diubah.

## Pemasangan

1. Backup proyek atau buat branch baru.
2. Ekstrak patch ke root proyek Ananta dan izinkan file yang sama digabung/ditimpa.
3. Tambahkan environment variables backend:

```env
OPENAI_API_KEY=sk-...
PROFILING_OPENAI_MODEL=gpt-5.6-terra
PROFILING_OPENAI_TIMEOUT_SECONDS=300
PROFILING_RESEARCH_MAX_OUTPUT_TOKENS=14000
PROFILING_SYNTHESIS_MAX_OUTPUT_TOKENS=18000
PROFILING_BLOCKED_DOMAINS=reddit.com,quora.com,wikipedia.org
```

4. Redeploy backend dan frontend.
5. Buka halaman Asisten AI.
6. Ketik `/profiling Nama Orang`.

## Perilaku sistem

- Slash command dikenali di endpoint `/api/v1/ai/chat`.
- Nama saja merupakan input minimum.
- Bila identitas ambigu, agent tidak boleh menggabungkan kandidat atau menebak.
- Riset memakai OpenAI Responses API dan tool `web_search`.
- Output disimpan sebagai pesan asisten di percakapan yang sama.
- Sumber URL dibuat dapat diklik oleh komponen chat.
- Hasil selalu diberi status review manusia sebelum dipakai sebagai data final.
- Pilihan model Claude pada dropdown tidak dipakai untuk slash command; modul profiling otomatis memakai model OpenAI yang dikonfigurasi.

## Tidak memerlukan migrasi database

Riwayat tetap memakai:

```text
AiConversation
AiMessage
```

Jadi patch versi slash command ini tidak memakai tabel `profiling_reports` dari rancangan halaman terpisah sebelumnya.
