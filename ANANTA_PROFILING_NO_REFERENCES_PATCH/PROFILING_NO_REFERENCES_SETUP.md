# PROFILING 2.0 — Mode Stabil Tanpa Referensi

Patch ini dipasang di atas versi slash command `/profiling` yang sudah aktif.

## Perubahan utama

- Tidak menampilkan bagian `SUMBER`.
- Tidak menampilkan kode `[S1]`, `[S2]`, dan seterusnya.
- Tidak menampilkan URL gambar atau halaman sumber pada chat.
- Pencarian sumber tetap dilakukan secara internal oleh OpenAI Web Search.
- Proses lama dua tahap diubah menjadi satu Responses API call.
- Pencarian gambar dimatikan untuk slash command.
- Search context diubah menjadi `low`.
- Reasoning profiling dikunci pada `medium`.
- Retry internal diubah menjadi `0` agar request tidak terlalu lama saat upstream gagal.
- Output JSON dibatasi agar tidak terlalu panjang.

## File yang ditimpa

Salin isi ZIP ke root proyek Ananta dan izinkan replace untuk:

```text
backend/app/services/profiling.py
backend/app/core/config.py
backend/app/routers/ai_chat.py
backend/.env.example
```

File pengujian baru:

```text
backend/tests/test_profiling_no_references.py
```

Tidak ada perubahan frontend, database, SQL, sidebar, atau package.json.

## Railway Variables

Buka Railway > Backend Service > Variables, lalu set:

```env
PROFILING_OPENAI_MODEL=gpt-5.6-terra
PROFILING_OPENAI_TIMEOUT_SECONDS=180
PROFILING_OPENAI_MAX_RETRIES=0
PROFILING_SEARCH_CONTEXT_SIZE=low
PROFILING_OPENAI_EFFORT=medium
PROFILING_OUTPUT_MAX_TOKENS=9000
PROFILING_BLOCKED_DOMAINS=reddit.com,quora.com,wikipedia.org
```

`OPENAI_API_KEY` tetap wajib tersedia.

Variabel lama berikut sudah tidak dipakai oleh versi satu tahap dan boleh dihapus agar tidak membingungkan:

```env
PROFILING_RESEARCH_MAX_OUTPUT_TOKENS
PROFILING_SYNTHESIS_MAX_OUTPUT_TOKENS
PROFILING_MAX_CANDIDATE_SOURCES
PROFILING_MAX_DISPLAYED_SOURCES
```

## Deploy

1. Backup/commit proyek.
2. Ekstrak patch ke root proyek.
3. Pastikan Railway Variables sesuai daftar di atas.
4. Redeploy backend saja.
5. Uji:

```text
/profiling Noor Maghantara, S.I.K., M.Si.
```

Untuk nama yang berpotensi ambigu:

```text
/profiling Nama | Jabatan | Instansi | Wilayah | Periode
```

## Hasil yang diharapkan

Hasil tetap memiliki identitas, pendidikan, riwayat jabatan, penghargaan, berita, data terkonfirmasi, konflik, dan catatan kualitas. Namun hasil tidak lagi memuat:

```text
[S1]
[S2]
SUMBER
https://alamat-referensi...
```

## Catatan 502

Patch ini mengurangi penyebab utama 502 dari sisi aplikasi: dua panggilan AI menjadi satu, tanpa image search, konteks lebih kecil, output lebih ringkas, dan tanpa retry panjang. Jika 502 tetap muncul, periksa log Railway untuk memastikan apakah gateway hosting atau OpenAI upstream yang menutup koneksi.
