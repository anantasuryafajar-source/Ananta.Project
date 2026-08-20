# Ringkasan perubahan

## `backend/app/services/profiling.py`

- Menggunakan satu Responses API call dengan Web Search + Structured Output.
- Menambahkan `PROFILE_SCHEMA_NO_REFERENCES` tanpa `source_ids`.
- Menghapus bibliografi dan kode referensi dari renderer.
- Menghapus URL foto dan halaman sumber dari dokumen chat.
- Membatasi jumlah item pada bagian profil.
- Response backend tidak lagi membawa katalog sumber atau research excerpt.

## `backend/app/core/config.py`

Default baru:

```text
PROFILING_OPENAI_TIMEOUT_SECONDS=180
PROFILING_OPENAI_MAX_RETRIES=0
PROFILING_SEARCH_CONTEXT_SIZE=low
PROFILING_OPENAI_EFFORT=medium
PROFILING_OUTPUT_MAX_TOKENS=9000
```

## `backend/app/routers/ai_chat.py`

- Slash command memanggil profiling dengan `include_images=False`.

## Pengujian

- Schema final tidak memiliki `source_ids`.
- Dokumen tidak memiliki `SUMBER`, `[S1]`, URL foto, atau halaman sumber.
- Pengaturan lightweight aktif.
- Parser slash command tetap berfungsi.
