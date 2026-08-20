# Bot langkah 7 — /pengadaan (faktur pembelian, multi-baris)

Perintah paling kompleks: satu-satunya yang menggerakkan STOK + JURNAL sekaligus.
Data masuk lewat service `create_and_post_bill` Ananta.

## Desain: sekali-kirim + konfirmasi wajib
Menghindari "pemilih" rumit. Pengguna kirim supplier + baris item (pakai SKU).
Bot MERESOLUSI semua (supplier by nama, produk by SKU), menampilkan RINGKASAN
lengkap, lalu baru menyimpan setelah ketik YA. Konfirmasi = jaring pengaman
sebelum menyentuh stok/jurnal.

## File berubah
- `backend/app/bot/handlers.py` — /pengadaan
- `backend/app/bot/parsing.py` — parse_pengadaan_block, parse_item_line (tambahan)
- `backend/tests/test_bot_parsing.py` — test CI (tambahan)

Tidak ada migrasi / kolom / env baru.

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/
git commit -m "bot langkah 7: /pengadaan"
git push
```
Tonton Railway "Healthcheck succeeded" & CI GitHub hijau.

## Cara pakai
Butuh peran warehouse atau finance (owner selalu lolos).

```
/pengadaan
Supplier: PT Sumber Minuman
Gudang: Gudang Utama          (opsional)
Item: MNS-WHK x 10 @ 250000
Item: CLA-AZL x 5 @ 800000
```
- Tiap Item: `SKU x jumlah @ harga_beli`. Boleh banyak baris Item.
- Bot menampilkan ringkasan (nama produk x qty @ harga = subtotal, + total).
  Ketik YA untuk simpan.

## Penanganan kesalahan (tidak menyimpan bila ada yang salah)
- Supplier tidak ditemukan / ambigu -> bot minta perbaiki (bukan asal pilih).
- SKU tidak ditemukan -> bot sebutkan SKU-nya, batal simpan.
- Baris salah format -> bot tunjukkan baris ke berapa.

## Catatan
- Supplier & produk harus SUDAH ada (pakai /tambah_kontak & /tambah_produk).
- Gudang opsional; bila 1 gudang saja, otomatis dipakai.
- Harga = harga beli (unit_cost). Jurnal & stok ditangani service Ananta.

## Tersisa dari Bagian 3 spec
- /input_transaksi (omzet lempar/collect) — paling kompleks, ditunda.
