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

Domainnya spesifik: PT ASF, distributor minuman impor. CoA, 25 SKU, dan 54 customer di
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
   agregat/cache saldo. Di `reports._balances`, penyaringan tanggal HARUS terjadi di
   subquery sebelum penjumlahan — pernah salah dipasang di klausa `ON` sebuah
   `LEFT JOIN` ke `journals`, dan karena nominalnya diambil dari `JournalEntry` yang
   sudah ikut lewat join sebelumnya, baris di luar periode tidak terbuang: setiap
   periode Laba Rugi menampilkan angka seumur hidup perusahaan dan `as_of` di
   Neraca diabaikan. Diperbaiki 2026-08-20.
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

### Aturan ketiga: komisi adalah kesepakatan internal, bukan bagian dari harga

Diputuskan client 2026-08-20. Tiga aturannya saling mengunci — melanggar satu
merusak dua yang lain. Penjaganya `tests/test_commission.py`.

1. **Komisi hanya berlaku di kasus tertentu dan nilainya beda-beda.** Karena itu
   TIDAK ada rate global dan tidak ada perhitungan otomatis: `SalesCommission.amount`
   diketik per kasus dan itulah sumber kebenarannya. `basis`/`rate` cuma catatan
   cara menghitungnya waktu itu. Jangan bikin fitur "hitung ulang komisi dari
   master" — modal master berubah, angka kesepakatan lama ikut bergeser.
2. **Komisi tidak boleh muncul di faktur.** Faktur adalah dokumen yang dilihat
   customer dan harganya harus harga sebenarnya. Karena itu komisi ada di tabel
   `sales_commissions` sendiri, bukan kolom di `invoices`/`invoice_lines`. Dua
   jalur kebocoran yang harus dijaga: markup diam-diam di `unit_price`, dan
   komisi dititipkan ke `discount`.
3. **Komisi diakui saat NILAINYA DISEPAKATI** — basis AKRUAL, dua jurnal:
   `create_commission()` memposting `Dr 6-1100 Beban Komisi / Cr 2-1600 Utang
   Komisi` (ini yang masuk Laba Rugi), lalu `pay_commission()` memposting
   `Dr 2-1600 / Cr Kas-Bank` (neraca saja). `pay_commission` TIDAK BOLEH
   mendebit 6-1100 — kalau itu terjadi, komisinya terhitung dua kali.
   Titik pengakuannya "saat disepakati" dan bukan "saat faktur terbit" karena
   nilainya sering belum diketahui waktu faktur keluar, dan angka yang belum ada
   tidak bisa dijurnal. `void_commission` membalik KEDUA jurnal — membalik
   pengakuan saja meninggalkan utang komisi menggantung.
   Basis kas dipakai sebentar pada 2026-08-20 lalu diganti akrual di hari yang
   sama, karena komisi terutang tidak muncul di neraca sama sekali. Komisi lama
   dari era itu ditambal `python -m app.backfill_komisi_akrual` (dry run dulu,
   baru `--terapkan`) — sengaja bukan migrasi, karena menambah beban ke periode
   yang mungkin sudah dilaporkan harus dilihat manusia.

`/reports/commission` yang lama (rate rata × margin semua SKU) **bukan** angka
komisi sebenarnya; ia sekarang dilabeli **Simulasi Komisi** di UI. Angka nyata
ada di `/commissions/report`, dan hanya `total_dibayar` yang bisa dicocokkan
dengan akun 6-1100 di Laba Rugi.

**Masih terbuka:** `reports_ext.commission` dan `reports_ext.gpm` menghitung modal
dari `Product.purchase_price` (modal ACUAN dari master ÷ isi dus), sementara HPP di
laba-rugi memakai `avg_cost` NYATA. Jadi margin di dua laporan itu bisa berbeda
untuk penjualan yang sama — perilaku lama yang sengaja mengikuti sheet KOMISI
client. Sekarang risikonya lebih kecil karena komisi tidak lagi diturunkan dari
angka itu (cuma dipakai sebagai saran di form), tapi jangan "perbaiki" sepihak.

### Aturan keempat: cara membayar tidak menyentuh cara mengakui

Rancangan lengkapnya di `RANCANGAN-KUSTOMISASI.md`. Penjaganya
`tests/test_receivable_terms.py`.

1. **Jurnal penjualan seragam untuk SEMUA kesepakatan pembayaran** — tunai,
   tempo, DP, atau tagih di PO berikutnya menghasilkan jurnal faktur yang persis
   sama. Variasinya hanya menyentuh akun NERACA lewat `advance_service` dan
   `terms_service`. Karena itu Laba Rugi tidak perlu tahu ada variasi, dan mode
   pembayaran baru tidak akan pernah bisa merusaknya. Jangan pernah membuat
   `invoice_service` bercabang berdasarkan cara bayar.
2. **DP masuk lewat `advance_service`, TIDAK lewat `payment_service`.** Yang
   terakhir selalu mengkredit Piutang Usaha; dipakai untuk uang yang masuk
   sebelum faktur ada, piutang jadi minus dan pendapatannya tak punya lawan.
   DP = `Dr Kas / Cr Uang Muka Pelanggan (2-1500)`, lalu dialokasikan ke faktur
   dengan `Dr Uang Muka / Cr Piutang`. PPN tidak dipungut saat DP diterima
   (keputusan client 2026-08-20); kalau berubah, jadikan flag, jangan hardcode.
3. **Kelebihan DP tetap kewajiban**, bukan piutang negatif. `allocate_to_invoice`
   menolak alokasi yang melebihi sisa piutang faktur.
4. **Setiap faktur SELALU punya `invoice_terms`.** `create_and_post_invoice`
   membuatnya otomatis dari `Contact.payment_term_days` bila `terms` tidak
   dikirim, jadi `ar_aging` tidak pernah perlu menebak dari tanggal faktur.
   Jalur cadangan untuk faktur tanpa jadwal masih ada di `ar_aging` sebagai
   pengaman, tapi seharusnya tidak pernah terpakai pada data baru.
5. **`invoice_terms` wajib berjumlah persis `Invoice.total`.** Ditegakkan di
   `terms_service.set_terms`. Jadwal yang boleh berbeda dari faktur membuat AR
   Aging melaporkan angka yang tidak pernah cocok dengan Neraca, tanpa error.
6. **`due_date` NULL berarti belum ada tanggal**, bukan jatuh tempo hari faktur.
   `reports.ar_aging` menaruhnya di ember `tanpa_tempo` — kalau tidak, kesepakatan
   "tagih saat order berikutnya" terbaca menunggak 90+ hari dan orang menagih
   customer yang tidak terlambat.
7. **Tarif ongkir di `persen_margin_min_ongkir` BUKAN dari `courier_expenses`.**
   `CommissionScheme.ongkir_per_dus` adalah tarif KESEPAKATAN dengan sales;
   `courier_expenses.amount` adalah ongkir AKTUAL yang dibayar ke ekspedisi.
   Keduanya sering berbeda dan tidak boleh saling menggantikan — memakai yang
   salah berarti orang dibayar keliru. Jumlah dus dihitung PECAHAN (18 botol
   dari dus isi 12 = 1,5 dus), bukan dibulatkan ke atas; itu keputusan bisnis,
   dikunci di `test_dus_dihitung_pecahan_bukan_dibulatkan`.
8. **Skema komisi & termin adalah daftar TERTUTUP.** Tipe `manual` (komisi) dan
   `custom` (termin) adalah pintu darurat yang menyimpan ANGKA, bukan aturan —
   keduanya tidak menghitung apa pun. Jangan pernah membuatnya menerima rumus
   yang dieksekusi sistem: begitu rumus bisa diketik user, angkanya berhenti bisa
   dijelaskan dan tidak bisa dites. Tambah tipe baru bernama jelas saja.
9. **Skema di-snapshot ke baris komisi** (`scheme_type`, `scheme_value`), sama
   seperti `unit_factor`. Jangan membaca ulang tarif dari master saat melapor.

Catatan UI: satu faktur kini menghasilkan BEBERAPA baris di AR Aging (satu per
termin belum lunas), jadi kunci baris React harus menyertakan `term_sequence` —
nomor faktur saja akan duplikat.

Tes invarian yang paling menentukan: `test_saldo_piutang_cocok_dengan_neraca` —
total outstanding AR Aging harus sama persis dengan saldo akun 1-1200 di Neraca.
Sepadan dengan tes valuasi stok vs akun Persediaan. Kalau gagal, ada jalur uang
yang salah akun.

### Aturan kelima: yang custom itu transaksinya, jurnalnya tetap riil

Lembar Hitung (`profit_sheets`) — kalkulator kesepakatan yang menempel di
faktur. Rancangan di `RANCANGAN-LEMBAR-HITUNG.md`, penjaganya
`tests/test_profit_sheet.py`.

1. **Lembar tidak pernah menyentuh Pendapatan, HPP, atau Persediaan.** Yang
   dijurnal cuma hasilnya: `Dr Beban Bagi Hasil (6-1300) / Cr Utang Bagi Hasil
   (2-1700)` dan `Dr Beban Komisi / Cr Utang Komisi`. Kalau ada yang menambah
   `Line()` ke akun pendapatan/HPP/persediaan di `profit_sheet_service`, laba
   kotor jadi bisa terkontaminasi kesepakatan dan aturan anti-double-counting
   client batal.
2. **`hpp_riil` dibaca dari `journal_entries`**, bukan dihitung ulang dari
   stok — avg_cost sudah bergerak sejak faktur diposting. Dan sengaja TIDAK
   bisa ditimpa user: kalau bisa, lembar berhenti bisa dipakai memeriksa
   pembukuan. Yang boleh ditimpa `hpp_dasar_komisi`, dan selisihnya
   ditampilkan berdampingan.
3. **Hidden margin TIDAK dijurnal.** Ia turunan: `penjualan − hpp_riil −
   bagian mitra`. Menjurnalnya sebagai pendapatan terpisah bikin laba dobel
   dan persediaan melenceng.
4. **`bagian_asf` WAJIB dievaluasi setelah semua baris `profit_bersama`.**
   Kalau dibalik, komisi pihak ketiga terhitung dari profit bersama dan
   nilainya dua kali lipat (4%×300=12, benarnya 4%×150=6). Angkanya tetap
   masuk akal, jadi tidak akan ketahuan sampai ada yang protes bayarannya.
   Dikunci di `test_komisi_pihak_ketiga_dari_bagian_asf_bukan_profit_bersama`.
5. **Bagian mitra adalah BEBAN, bukan pembagian laba di bawah garis.** Dari
   angka client: omzet 1.000 − HPP 600 − Andre 150 = 250 = hidden margin 100 +
   bagian ASF 150. Angka 250 hanya keluar kalau 150-nya mengurangi laba.
6. **Transfer terkunci sampai `invoice.status == "paid"`** — status, bukan
   jurnal. Beban sudah diakui saat lembar disetujui.
7. **`void_sheet` wajib dipakai untuk faktur yang tak akan pernah lunas.**
   Tanpa itu, Utang Bagi Hasil & Utang Komisi menumpuk selamanya dengan angka
   yang tidak akan pernah dibayar.
8. **Daftar `DASAR` tertutup.** Custom = user mengetik ANGKA (modal
   perjanjian, persen, pengurang). Custom ≠ user mendefinisikan RUMUS. Dasar
   `nominal` adalah pintu darurat yang menyimpan angka, bukan aturan.

Catatan nama: `pengurang_per_dus` sempat bernama `ongkir_per_dus` (0008) dan
itu keliru — angka ini murni variabel pengurang komisi, tidak ada hubungannya
dengan `courier_expenses` dan tidak pernah masuk jurnal. Diganti di 0009.

### Aturan keenam: satu jenis hak, satu titik pengakuan

Empat jenis uang keluar, dan masing-masing diakui di titik BERBEDA. Salah
menaruhnya bikin beban dobel atau mendahului uangnya masuk.

| Jenis | Diakui kapan | Jurnal | Kode |
|---|---|---|---|
| Komisi pihak ketiga | lembar hitung disetujui | 6-1100 / 2-1600 | `profit_sheet_service` |
| Hak mitra (Andre) | lembar hitung disetujui | 6-1300 / 2-1700 | `profit_sheet_service` |
| Insentif penjualan | tiap cicilan masuk | 6-1400 / 2-1800 | `payout_service` |
| Bagi hasil omzet | tutup buku bulanan | 6-1500 / 2-1900 | `payout_service` |

1. **Komisi TIDAK boleh diakrual ulang per cicilan.** `approve_sheet` sudah
   mengakuinya penuh. Prorata untuk komisi hanya menentukan berapa yang boleh
   DITRANSFER (`payout_service.porsi_komisi_cair` — fungsi murni, tidak
   membuat jurnal). Dijaga `test_komisi_tidak_terjurnal_dua_kali`.
2. **Insentif JUSTRU diakrual per cicilan**, karena dasarnya uang masuk
   bersih. Mengakuinya saat faktur terbit = mengakui beban atas uang yang
   belum tentu masuk. `payment_service.receive_payment` memanggil
   `accrue_insentif_untuk_pembayaran` DI DALAM transaksi yang sama — kalau
   akrualnya gagal, pembayarannya ikut batal, bukan diam-diam terlewat.
   Dasarnya dipotong pengurang dari lembar hitung faktur itu; cicilan pelunas
   menyerap sisa pembulatan supaya jumlahnya persis (Total − Pengurang).
3. **Gerbang target butuh DUA syarat** (omzet ≥ 500jt DAN uang masuk bersih ≥
   500jt). `or` di situ mencairkan ratusan juta atas penjualan yang uangnya
   belum masuk.
4. **Term 1 sudah cair tgl 16 tidak pernah ditarik kembali** walau target
   meleset; yang hangus cuma Term 2 dan booster.
5. **Angka tutup buku disusun SERVER** lewat `build_month_data`, bukan
   dikirim UI. Kalau UI yang menjumlahkan omzet & uang masuk, dua tempat bisa
   berbeda dan tidak ada yang tahu mana yang benar.
6. **`close_month(terapkan=False)` adalah bawaan** — pratinjau tanpa jurnal.
   Tutup buku memindahkan ratusan juta; harus dilihat orang, bukan otomatis.
   Aman diulang: periode+penerima yang sudah diakrual dilewati.
7. **Bagi hasil omzet diperlakukan BEBAN**, bukan pengurang ekuitas, karena
   modelnya revenue share/royalty (flat 18%+14% atas omzet, tidak bergantung
   laba). Kalau suatu saat ini benar dividen pemegang saham, akunnya pindah
   ke ekuitas dan laba bersih semua periode lampau berubah.
8. **Dividen dihitung dari omzet KOTOR** — sesuai kesepakatan client, dan
   memang bisa melampaui laba. `generate_monthly_closing_report` memunculkan
   peringatan kalau `laba_kotor` diisi dan total transfer melebihinya. Itu
   alat kontrol, bukan penghalang: modul melapor, finance memutuskan.

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

Ada dua revisi dan keduanya penting:
- `0001_baseline.py` — `create_all()` dari model, jadi database BARU langsung lengkap.
- `0002_satuan_dus_botol.py` — mengejar ketertinggalan database yang lahir SEBELUM
  Alembic dipakai (skemanya dulu dibuat `create_all` di dalam seed, sehingga tidak
  punya kolom satuan). Karena 0001 sudah membuat kolom itu di database baru, seluruh
  operasi 0002 **dijaga dengan inspector** supaya jadi no-op alih-alih gagal. Pola
  ini akan diperlukan lagi setiap kali revisi harus jalan di dua jenis database.

Untuk database yang sudah terisi dan akunnya ingin dipertahankan, **jangan reset**:
`alembic upgrade head` lalu `python -m app.master_asf --terapkan` (selaraskan master
25 produk; idempoten, tidak menghapus produk apa pun, tidak menyentuh stok/jurnal).

Reset TOTAL (buang semua data termasuk akun pengguna — password tidak bisa dipulihkan
karena hash Argon2, tautan bot Telegram harus dibuat ulang):
`alembic downgrade base && alembic upgrade head && python -m app.seed_asf`.
Destruktif — pastikan memang diminta, dan `pg_dump` dulu.

## Struktur frontend
Route group `app/(app)/` = halaman aplikasi ber-sidebar (`lib/nav.ts` adalah satu-satunya
sumber daftar menu), `app/(auth)/` = login/lupa-password. Direktori `app/login/`,
`app/forgot-password/`, `app/reset-password/` kosong dan merupakan sisa refactor.
Design system "Calm Ledger": token semantik CSS di `app/globals.css` (`bg-canvas`,
`text-ink`, `border-line`, `bg-primary-soft`, `var(--radius-card)`) — pakai token, jangan
warna Tailwind mentah.
