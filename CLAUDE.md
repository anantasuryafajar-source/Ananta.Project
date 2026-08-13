# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Catatan bahasa: seluruh kode, komentar, docstring, pesan error, dan label UI di repo ini
berbahasa Indonesia. Ikuti konvensi itu untuk kode baru.

## Perintah

### Frontend (root repo)
```bash
npm install
npm run dev            # http://localhost:3000 (turbopack)
npm run build          # next build — dipakai Vercel
```
`npm run lint` ada di `package.json` tetapi **belum bisa dipakai**: eslint tidak ada di
dependencies dan `next lint` sudah dihapus di Next 16. Untuk pemeriksaan tipe pakai
`npx tsc --noEmit`.

### Backend (`cd backend`)
```bash
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows
pip install uv
uv pip install -r pyproject.toml --group dev

alembic upgrade head                   # buat/ubah tabel (WAJIB sebelum seed)
python -m app.seed_asf                 # isi data awal PT ASF (idempoten)
uvicorn app.main:app --reload          # http://localhost:8000 · docs di /docs · /health

pytest                                 # semua tes (asyncio_mode=auto, pythonpath=".")
pytest tests/test_journal_balance.py                              # satu file
pytest tests/test_journal_balance.py::test_unbalanced_rejected    # satu tes
```
Tes memakai SQLite in-memory (`tests/conftest.py`), jadi tidak perlu Postgres berjalan.

Database lokal: `docker compose up -d db` dari root. Service `api` di
`docker-compose.yml` **rusak** (`build: ./apps/api` sudah tidak ada) — jangan dipakai.
Service `redis` juga tidak perlu; Redis ada di config tapi tidak dipakai kode mana pun.

Frontend memanggil `/api/v1/*` relatif dan `next.config.ts` mem-proxy-nya ke backend
**hanya bila `API_BASE` diset**. Tanpa env var itu, halaman tetap render normal tapi
semua request 404 tanpa pesan jelas — ini penyebab paling umum "login tidak jalan".

## Arsitektur

Tiga permukaan, satu repo:

| Bagian | Lokasi | Deploy |
|---|---|---|
| Web app Next.js 16 (App Router, React 19, Tailwind v4) | root | Vercel |
| API FastAPI + SQLAlchemy 2 async | `backend/` | Railway/Render (Docker) |
| Bot Telegram (python-telegram-bot, webhook) | `backend/app/bot/` | menempel di proses API |

Domainnya spesifik: PT ASF, distributor minuman impor. CoA, 18 SKU, dan 54 customer di
`app/seed_asf.py` adalah data riil dari `ASF_MASTER_DATA.xlsx`, bukan contoh generik.

### Aturan inti: jurnal adalah sumber kebenaran tunggal

Ini invarian terpenting sistem. Jangan langgar.

1. **Semua jurnal lewat `services/journal.py::post_journal()`.** Jangan pernah membuat
   `Journal`/`JournalEntry` langsung. Fungsi itu menegakkan debit==kredit, menolak nilai
   negatif, menolak satu baris debit+kredit sekaligus, dan menolak posting pada periode
   yang sudah ditutup (`Company.period_lock_date`).
2. **Pola setiap transaksi bisnis:** hitung total → `post_journal()` → mutasi stok/saldo →
   `commit()` di router; rollback bila gagal. Contoh lengkap ada di
   `services/invoice_service.py` (barang keluar: Piutang/Pendapatan/PPN + HPP/Persediaan)
   dan `services/purchase_service.py` (barang masuk: Persediaan/PPN Masukan/Utang +
   update average cost). Modul baru mengikuti pola ini.
3. **Laporan tidak boleh menyimpan angka.** `services/reports.py` dan `reports_ext.py`
   menghitung ulang dari `journal_entries` setiap kali dipanggil. Jangan tambah kolom
   agregat/cache saldo.
4. **Transaksi terposting tidak dihapus.** `services/void_service.py` membuat jurnal balik
   + mutasi stok balik dan menandai status `void`, agar jejak audit utuh.
5. **Uang selalu `Decimal` + `Numeric(18,2)`** (`Money` di `models/base.py`), kuantitas
   `Numeric(18,4)` (`Qty`). Tidak ada float untuk nilai uang.

Detail model yang mudah menjebak: `models/base.py` memaksa `type_annotation_map = {str:
String(36)}` dan PK `String(36)` eksplisit supaya tipe PK dan FK identik — tanpa itu
PostgreSQL menolak FK. Jangan ubah tanpa alasan kuat.

### Aturan kedua: satuan dus vs botol

Sama pentingnya dengan invarian jurnal. Aturan lengkapnya di `services/units.py`.

1. **Stok, HPP, dan valuasi HANYA dalam BOTOL** (satuan dasar). "Dus" adalah pengali
   saat input dan cara menampilkan — bukan satuan penyimpanan. Jangan pernah menambah
   penghitung dus terpisah; itu menciptakan dua sumber kebenaran untuk satu kenyataan
   fisik. Tampilan "1 dus 5 botol" dihasilkan `units.format_qty()` dari 29 botol.
2. **Isi per dus disimpan per produk** (`Product.pack_size`), bukan konstanta global.
   ASF: Chivas 200ml = 24, Robinson Vodka = 48, sisanya 12. Fallback global akan
   menghasilkan stok salah TANPA error saat ada SKU baru berkemasan lain.
3. **Modal diinput per DUS.** `Product.pack_purchase_price` = modal per dus (yang
   diketik, sumber kebenaran); `Product.purchase_price` = modal per botol (turunan,
   dipakai laporan margin). Label UI/bot harus eksplisit "per dus" — salah baca
   sebagai per botol membuat HPP salah 12–48x.
4. **Baris transaksi menyimpan `quantity` (botol), `qty_input` + `unit` (seperti
   diketik), dan `unit_factor` hasil SNAPSHOT.** Faktor tidak boleh dibaca ulang dari
   master saat melapor — kalau kemasan berubah, riwayat lama harus tetap berarti sama.
   `unit_price`/`unit_cost` adalah harga **per satuan yang dipilih** (harga dus punya
   diskon grosir sendiri, bukan 24x harga botol).
5. **Titik paling rawan:** `purchase_service` menghitung `avg_cost` = nilai baris ÷
   jumlah **botol**. Membaginya dengan jumlah dus merusak HPP, valuasi, dan neraca —
   dan karena HPP sudah terposting, koreksinya harus lewat jurnal manual.
6. **Konversi PO→Bill / SO→Invoice mengirim `qty_input` + `unit`**, bukan `quantity`.
   Mengirim `quantity` membuat faktor dikalikan dua kali (1 dus jadi 144 botol).
7. **Bot Telegram wajib satuan eksplisit** di `/jual` & `/pengadaan`
   (`SKU x 2 dus @ harga`). Baris tanpa satuan ditolak lewat `ItemUnitMissing` —
   menebak "botol" padahal maksudnya "dus" langsung salah 24x di jurnal.
8. **Harga jual tidak ada di master produk.** Berbeda tiap customer; diisi saat
   membuat faktur. Nilai awalnya dari `GET /invoices/last-prices?contact_id=` (harga
   terakhir customer itu per produk & satuan). `Product.sale_price` dipertahankan
   sebagai kolom acuan lama, biarkan 0.
9. **SKU dibuat otomatis** dari nama (`product_service.slug_sku`) dan tidak diketik
   user, tetapi tetap ada karena dipakai bot untuk membedakan produk bernama mirip
   (Macallan 12 DC/TC/SO) dan sebagai kunci laporan & import Excel.

10. **Biaya per satuan disimpan 4 desimal** (`UnitCost` di `models/base.py`):
    `StockLevel.avg_cost` & `StockMovement.unit_cost`. Pembagian dus→botol jarang
    bulat, dan dengan 2 desimal `qty × avg_cost` di laporan valuasi melenceng dari
    saldo akun Persediaan di jurnal. Nilai UANG yang masuk jurnal tetap 2 desimal.

Tes penjaga aturan ini: `tests/test_unit_conversion.py` — termasuk
`test_valuasi_stok_cocok_dengan_saldo_persediaan_di_jurnal`. Kalau file itu gagal,
jangan lanjut — angka akuntansinya sedang salah.

**Terbuka & menunggu keputusan client (per 2026-08-13):** `reports_ext.commission`
dan `reports_ext.gpm` menghitung modal dari `Product.purchase_price` (modal ACUAN
dari master ÷ isi dus), sementara HPP di laba-rugi memakai `avg_cost` NYATA. Jadi
margin di dua laporan itu bisa berbeda untuk penjualan yang sama — perilaku lama
yang sengaja mengikuti sheet KOMISI client. Jangan "perbaiki" sepihak: angkanya
menentukan komisi sales. Client belum membahas ini.

Penomoran dokumen memakai row-lock (`SELECT ... FOR UPDATE`) di `services/numbering.py`.
Resolusi akun default per perusahaan lewat kode CoA di `services/accounts_map.py`.

### Auth & RBAC
JWT (PyJWT) + Argon2. RBAC dicek **di backend** lewat `deps.py::require_roles(...)`, bukan
hanya di UI; peran `owner|finance|sales|warehouse|viewer`, dan `owner` selalu lolos.
Frontend menyimpan access token di `localStorage` (`lib/api.ts`); refresh token dibuat di
backend tapi **belum dipakai** frontend, jadi sesi mati setelah `ACCESS_TOKEN_MINUTES`.

### Lapisan AI
Alur: `User → Intent Detection → Prompt Registry → Model Router → GPT/Claude (+tools)`.

- `app/prompts/` — registry 11 mode; prompt final = `BASE_PROMPT` + prompt mode.
- `services/ai/intent.py` — dua lapis: heuristik kata kunci, lalu klasifikasi Haiku.
- `services/ai/router.py` — pilihan model user selalu menang; kalau `auto`, mode
  menentukan provider, dengan fallback bila salah satu API key kosong (instalasi
  OpenAI-only maupun Anthropic-only harus tetap jalan).
- `services/ai/tools.py` — tool baca data ASF, dipakai kedua provider.
- **PROFILING 2.0** (`services/profiling.py`) adalah agent terpisah lewat OpenAI Responses
  API + Structured Outputs, dipicu slash command `/profiling Nama | Jabatan | Instansi |
  Wilayah | Periode` di dalam chat (`routers/ai_chat.py`), bukan halaman sendiri. Ia
  melewati prompt umum karena punya guardrail publiknya sendiri, dan setiap fakta membawa
  status `confirmed|unconfirmed|conflicting|not_found` + confidence. Perubahan di sini
  sensitif terhadap timeout: default sengaja konservatif (`PROFILING_SEARCH_CONTEXT_SIZE=low`,
  `PROFILING_OPENAI_MAX_RETRIES=0`) agar request tidak melewati timeout proxy/frontend.
- Bot Telegram dan scheduler insight di-start dari `main.py` lifespan dengan try/except
  lebar — kegagalan keduanya **tidak boleh** menjatuhkan API atau `/health`. Pertahankan.

## Skema database

Skema dikelola **Alembic**. `entrypoint.sh` menjalankan `alembic upgrade head` lalu seed,
keduanya di background supaya `/health` cepat menjawab. Seed **tidak lagi** memanggil
`create_all()` dan tetap dilewati bila company sudah ada.

Menambah/mengubah model **wajib** disertai revisi (`alembic revision --autogenerate -m
"..."`). Dulu skema dibuat `create_all()` di dalam seed yang di-skip bila company sudah
ada — akibatnya model baru tidak pernah membuat tabelnya, dan itu sebabnya ada SQL manual
di `backend/migrations/*.sql`. File-file itu sekarang **historis**; isinya sudah tercakup
`alembic/versions/0001_baseline.py`.

`alembic/env.py` memakai `NORMALIZED_DATABASE_URL` dari `core/database.py`, bukan
`settings.DATABASE_URL` mentah — connection string Supabase membawa scheme `postgres://`
dan query `sslmode` yang membuat asyncpg gagal connect.

Reset TOTAL (buang semua data termasuk master):
`alembic downgrade base && alembic upgrade head && python -m app.seed_asf`.
Destruktif — pastikan memang diminta, dan `pg_dump` dulu bila datanya bukan dummy.

## Struktur frontend
Route group `app/(app)/` = halaman aplikasi ber-sidebar (`lib/nav.ts` adalah satu-satunya
sumber daftar menu), `app/(auth)/` = login/lupa-password. Direktori `app/login/`,
`app/forgot-password/`, `app/reset-password/` kosong dan merupakan sisa refactor.
Design system "Calm Ledger": token semantik CSS di `app/globals.css` (`bg-canvas`,
`text-ink`, `border-line`, `bg-primary-soft`, `var(--radius-card)`) — pakai token, jangan
warna Tailwind mentah.
