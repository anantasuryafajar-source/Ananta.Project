# Perbaikan: blok format lengkap kini dikenali di tengah alur terpandu

## Masalah sebelumnya
Kalau kamu kirim `/tambah_produk` polos dulu (bot masuk mode terpandu dan
bertanya "Masukkan SKU"), lalu menempel blok:
```
SKU: LKS
Nama: Lingatul kortisol
Satuan: botol
Harga: 0
```
bot menelan seluruh blok itu sebagai jawaban "SKU" saja, lalu bertanya "Nama".
Data tidak masuk. Itu bug UX.

## Perbaikan
Sekarang, bila di tengah alur terpandu kamu menempel blok yang memuat SKU DAN
Nama, bot langsung mengenalinya dan menyimpan produk sekaligus -- tidak lagi
memperlakukannya sebagai satu jawaban langkah.

Alur terpandu normal tetap jalan: mengetik jawaban tunggal (mis. hanya "EBN"
saat ditanya SKU) tetap diproses langkah-demi-langkah seperti biasa.

## Cara pakai yang benar (dua-duanya kini bekerja)
1. Kirim perintah + blok dalam SATU pesan:
   ```
   /tambah_produk
   SKU: LKS
   Nama: Lingatul kortisol
   Satuan: botol
   Harga: 0
   ```
2. Atau kirim `/tambah_produk` polos, lalu tempel blok di pesan berikutnya --
   sekarang ini juga langsung diproses.

## File berubah
- `backend/app/bot/handlers.py` (hanya ini)

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/app/bot/handlers.py
git commit -m "bot: kenali blok format lengkap saat alur terpandu aktif"
git push
```
Tonton Railway sampai "Healthcheck succeeded" & CI hijau. Webhook tak perlu disentuh.
