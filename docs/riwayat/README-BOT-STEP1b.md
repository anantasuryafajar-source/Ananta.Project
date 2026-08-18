# Tambahan: /tambah_produk mode sekali-kirim

Sekarang /tambah_produk punya DUA cara pakai (yang lama tetap jalan):

## 1) Sekali-kirim (baru) — cepat
Kirim satu pesan berisi perintah + format:
```
/tambah_produk
SKU: EBN
Nama: MINUMAN EBEN
Satuan: botol
Harga: 0
```
Bot langsung menyimpan dan membalas "Tersimpan: ...".

Toleran: boleh pakai tanda "-" di depan tiap baris, spasi bebas, dan harga
boleh pakai titik ribuan (mis. 250.000). Wajib ada SKU dan Nama; Satuan
default "pcs", Harga default 0 bila dikosongkan.

## 2) Terpandu (lama) — tetap ada
Kirim `/tambah_produk` polos (tanpa apa-apa di bawahnya), bot akan bertanya
satu per satu seperti biasa.

## File berubah
- `backend/app/bot/handlers.py` (hanya file ini)

## Deploy (PowerShell, dari root repo)
Extract ke root repo (menimpa handlers.py), lalu:
```powershell
git add backend/app/bot/handlers.py
git commit -m "bot: /tambah_produk dukung input sekali-kirim"
git push
```
Tonton Railway sampai "Healthcheck succeeded" dan CI GitHub hijau. Webhook tidak
perlu disentuh (sudah persisten). Setelah deploy, coba kirim format sekali-kirim
di atas.
