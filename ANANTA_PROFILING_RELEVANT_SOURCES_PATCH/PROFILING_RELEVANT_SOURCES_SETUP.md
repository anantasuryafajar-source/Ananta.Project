# Hotfix PROFILING 2.0 — Sumber Relevan dan Stabilitas 502

Patch ini dipasang setelah `ANANTA_PROFILING_SLASH_COMMAND_PATCH`.

## Tujuan

- Hanya menampilkan sumber yang benar-benar dirujuk oleh fakta dalam laporan final.
- Menghapus URL duplikat akibat `utm_source`, fragment, dan parameter tracking lain.
- Membatasi jumlah sumber pada tahap synthesis agar request tidak membengkak.
- Memprioritaskan sumber resmi/pemerintah dan sumber yang menyebut target secara langsung.
- Mengurangi risiko kegagalan sementara OpenAI 502/503/504 dengan satu kali retry.
- Tidak mengubah sidebar, frontend, database, atau format slash command.

## File yang perlu digabung

Salin isi patch ke root proyek Ananta:

```text
backend/app/services/profiling.py
backend/app/core/config.py
backend/.env.example
backend/tests/test_profiling_relevant_sources.py
```

Untuk proyek aktif, gunakan Compare/Merge pada `config.py` dan `.env.example` bila sudah ada perubahan lain.

## Railway Variables

Tambahkan atau ubah:

```env
PROFILING_SEARCH_CONTEXT_SIZE=medium
PROFILING_MAX_CANDIDATE_SOURCES=24
PROFILING_MAX_DISPLAYED_SOURCES=12
PROFILING_OPENAI_MAX_RETRIES=1
PROFILING_RESEARCH_MAX_OUTPUT_TOKENS=10000
PROFILING_SYNTHESIS_MAX_OUTPUT_TOKENS=16000
```

Variabel yang sudah ada tetap diperlukan:

```env
OPENAI_API_KEY=sk-...
PROFILING_OPENAI_MODEL=gpt-5.6-terra
PROFILING_OPENAI_TIMEOUT_SECONDS=300
PROFILING_BLOCKED_DOMAINS=reddit.com,quora.com,wikipedia.org
```

## Perilaku baru

1. Web search tetap boleh menemukan banyak halaman secara internal.
2. Sistem memilih maksimum 24 sumber terbaik untuk tahap penyusunan.
3. Structured Output hanya boleh merujuk ID dari katalog terpilih tersebut.
4. Setelah profil selesai, sistem menghitung `source_ids` yang benar-benar digunakan.
5. Chat hanya menampilkan sumber yang digunakan, maksimum 12.
6. Setiap fakta menampilkan maksimum 3 sumber pendukung.
7. Fakta `confirmed` tanpa sumber yang valid otomatis diturunkan menjadi `unconfirmed`.

## Tidak perlu dilakukan

- Tidak perlu menjalankan SQL.
- Tidak perlu membuat tabel baru.
- Tidak perlu mengubah sidebar.
- Tidak perlu mengubah halaman Asisten AI.
- Tidak perlu menambah package npm atau Python.

## Pengujian

Setelah redeploy, gunakan target dengan konteks agar identitas tidak ambigu:

```text
/profiling Dedi Prasetyo | Wakapolri | Polri | Indonesia | 2025-sekarang
```

Periksa bagian `SUMBER`. Jumlahnya seharusnya jauh lebih sedikit dan setiap ID harus muncul pada fakta, pendidikan, jabatan, berita, foto, atau konflik dalam laporan.

## Tuning

Untuk hasil lebih ringkas:

```env
PROFILING_MAX_CANDIDATE_SOURCES=18
PROFILING_MAX_DISPLAYED_SOURCES=8
PROFILING_SEARCH_CONTEXT_SIZE=low
```

Untuk riset lebih luas tetapi output tetap ringkas:

```env
PROFILING_MAX_CANDIDATE_SOURCES=30
PROFILING_MAX_DISPLAYED_SOURCES=12
PROFILING_SEARCH_CONTEXT_SIZE=high
```

Rekomendasi produksi awal tetap `24`, `12`, dan `medium`.
