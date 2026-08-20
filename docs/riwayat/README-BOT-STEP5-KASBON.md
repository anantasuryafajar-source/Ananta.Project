# Bot langkah 5 — /kasbon (pinjaman karyawan)

Menambah perintah /kasbon. Memposting jurnal Dr Kasbon / Cr Kas-Bank lewat
service `create_loan` Ananta yang sudah ada.

## File berubah
- `backend/app/bot/handlers.py` — perintah /kasbon
- `backend/app/bot/parsing.py` — parse_loan_block (tambahan)
- `backend/tests/test_bot_parsing.py` — test CI (tambahan)

Tidak ada migrasi / kolom / env baru.

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/
git commit -m "bot langkah 5: /kasbon"
git push
```
Tonton Railway "Healthcheck succeeded" & CI GitHub hijau.

## Cara pakai
Butuh peran finance (owner selalu lolos).

### Terpandu
`/kasbon` polos: nama karyawan -> jumlah -> sumber bayar (nomor) -> YA.

### Sekali-kirim
```
/kasbon
Nama: Budi
Jumlah: 500000
Bayar: kas
```
Nama & Jumlah wajib. Bayar opsional (default Kas). Bayar: kas/bca/ocbc.

## Verifikasi
Bot membalas nomor kasbon. Cek web Ananta -> menu Kasbon. Karena memposting
jurnal, angka juga tampak di Buku Besar (Dr Kasbon / Cr Kas).

## Berikutnya (tier lebih sulit)
- /pengadaan, /payment_supplier, /payment_customer — perlu desain "pemilih"
  (cari & pilih supplier / faktur / produk lewat chat).
