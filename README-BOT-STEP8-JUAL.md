# Bot langkah 8 — /jual (faktur penjualan / Omzet Lempar)

Melengkapi /input_transaksi spec. "Omzet Collect" (uang masuk) sudah = /bayar_customer.
Yang baru di sini: "Omzet Lempar" = faktur penjualan keluar, lewat service
`create_and_post_invoice` Ananta. Menggerakkan STOK (keluar) + JURNAL
(Dr Piutang / Cr Penjualan + Dr HPP / Cr Persediaan).

Ini cerminan /pengadaan (customer, bukan supplier; unit_price, bukan unit_cost).

## File berubah
- `backend/app/bot/handlers.py` — /jual
- `backend/app/bot/parsing.py` — parse_penjualan_block (tambahan)
- `backend/tests/test_bot_parsing.py` — test CI (tambahan)

Tidak ada migrasi / kolom / env baru.

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/
git commit -m "bot langkah 8: /jual (Omzet Lempar)"
git push
```
Tonton Railway "Healthcheck succeeded" & CI GitHub hijau.

## Cara pakai
Butuh peran sales atau finance (owner selalu lolos).
```
/jual
Customer: Toko Berkah
Gudang: Gudang Utama          (opsional)
Item: MNS-WHK x 2 @ 300000
Item: CLA-AZL x 1 @ 950000
```
- Tiap Item: SKU x jumlah @ harga_jual. Boleh banyak baris.
- Bot menampilkan ringkasan -> ketik YA untuk simpan.
- Sama seperti /pengadaan: bila supplier/SKU/format salah, TIDAK disimpan.

## Alur lengkap Omzet (kini utuh via bot)
1. /jual  -> faktur penjualan keluar (Omzet Lempar).
2. /bayar_customer -> uang masuk atas faktur itu (Omzet Collect).

## Verifikasi
Cek web Ananta -> menu Penjualan, stok produk (berkurang), Buku Besar
(Dr Piutang / Cr Penjualan + Dr HPP / Cr Persediaan).

## Status Bagian 3 spec
SELESAI. Semua perintah input & pembayaran kini jalan lewat bot:
tambah_produk, tambah_pengeluaran, tambah_kontak, kasbon, pengadaan, jual,
bayar_supplier, bayar_customer (+ link, buat_kode).
