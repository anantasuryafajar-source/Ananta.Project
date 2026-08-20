# Perubahan Hotfix Sumber PROFILING 2.0

## `backend/app/services/profiling.py`

- Canonical URL dan deduplikasi parameter tracking.
- Skor kualitas sumber dan prioritas domain resmi.
- Batas katalog sebelum synthesis.
- Filter sumber berdasarkan `source_ids` yang benar-benar digunakan.
- Batas tiga sumber per fakta dan batas sumber akhir yang ditampilkan.
- Search context default diturunkan dari `high` menjadi `medium`.
- Image search maksimum dua hasil.
- Satu kali retry untuk status sementara 408/429/500/502/503/504.
- Read timeout tidak diulang agar request tidak semakin lama.
- Research prompt melarang daftar semua hasil pencarian dan membatasi kandidat ambigu.

## `backend/app/core/config.py`

Menambahkan:

- `PROFILING_OPENAI_MAX_RETRIES`
- `PROFILING_SEARCH_CONTEXT_SIZE`
- `PROFILING_MAX_CANDIDATE_SOURCES`
- `PROFILING_MAX_DISPLAYED_SOURCES`

Menurunkan default output token research/synthesis agar lebih stabil.

## `backend/tests/test_profiling_relevant_sources.py`

Menguji:

- Penghapusan tracking URL.
- Prioritas sumber resmi.
- Batas katalog sumber.
- Hanya sumber yang dirujuk yang ditampilkan.
- Maksimum sumber per fakta.
