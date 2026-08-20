# Bot langkah 3 — /tambah_pengeluaran (input pengeluaran + jurnal)

Menambah perintah /tambah_pengeluaran. Data masuk lewat service `create_expense`
Ananta yang sudah ada -> otomatis memposting jurnal (Dr Beban / Cr Kas/Bank),
dijaga invarian debit=kredit + CI.

## PENTING: paket ini KUMULATIF (memuat langkah 2 juga)
Karena langkah 2 & 3 sama-sama mengubah `handlers.py`, paket ini otomatis
menyertakan kode langkah 2 (penautan multi-pengguna). Itu berarti:

- Migrasi SQL langkah 2 **WAJIB dijalankan** (menambah kolom ke tabel users).
  Kalau dilewati, query users (termasuk LOGIN) akan gagal.
- Fitur multi-user ikut ter-deploy tapi **DORMAN** — kamu tidak perlu akun
  Telegram kedua. Ia hanya diam sampai suatu saat kamu menautkan orang lain.

## File berubah / baru
- `backend/app/bot/handlers.py` — perintah /tambah_pengeluaran (+ kode langkah 2)
- `backend/app/bot/parsing.py` — helper parsing pengeluaran (BARU)
- `backend/app/models/user.py` — kolom kode tautan (dari langkah 2)
- `backend/tests/test_bot_parsing.py` — test CI (BARU)
- `backend/migrations/telegram_step2_linkcode.sql` — migrasi langkah 2 (WAJIB)

## Urutan deploy
1. Supabase -> SQL Editor -> jalankan `telegram_step2_linkcode.sql` (WAJIB, idempotent).
2. Extract ke root repo, lalu:
   ```powershell
   git add backend/
   git commit -m "bot langkah 3: /tambah_pengeluaran (+ langkah 2 dorman)"
   git push
   ```
3. Tonton Railway sampai "Healthcheck succeeded" & CI GitHub hijau
   (ada test baru `test_bot_parsing`).

## Cara pakai /tambah_pengeluaran
Butuh peran finance (owner selalu lolos).

### Terpandu
Kirim `/tambah_pengeluaran` polos. Bot menanya berurutan:
Jumlah -> Keterangan -> pilih kategori beban (ketik nomor) ->
pilih sumber bayar Kas/BCA/OCBC (ketik nomor) -> ketik YA.

### Sekali-kirim
```
/tambah_pengeluaran
Jumlah: 150000
Untuk: Bensin operasional
Beban: bensin
Bayar: kas
```
- Jumlah & Untuk wajib. Beban & Bayar opsional (default: Operasional Lainnya
  6-2900 & Kas 1-1000).
- "Beban" boleh kata kunci (bensin, ongkir, gaji, sewa, listrik, ...) atau kode
  langsung (mis. 6-2400). "Bayar" boleh kas/bca/ocbc atau kode.
- Harga boleh pakai titik ribuan (150.000).

## Verifikasi
Setelah simpan, bot membalas nomor pengeluaran. Cek di **web Ananta -> menu Biaya**.
Karena ini memposting jurnal, cek juga Laba Rugi / Buku Besar bila perlu -- angka
harus konsisten (invarian debit=kredit dijaga).

## Catatan
- Tanggal pengeluaran otomatis = hari ini (WIB).
- Semua tulisan lewat `create_expense` -> `post_journal` yang sama dengan web.
  Bot tidak pernah menulis jurnal mentah.
