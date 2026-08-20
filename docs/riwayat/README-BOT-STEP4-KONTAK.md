# Bot langkah 4 — /tambah_kontak (customer/supplier)

Menambah perintah /tambah_kontak. Master-data murni, TANPA jurnal. Data masuk
lewat service `create_contact` -> tabel contacts yang sama dengan web.

## Kenapa kontak dulu (bukan /pengadaan)
Audit menunjukkan /pengadaan butuh alur multi-entitas + multi-baris (pilih
supplier + gudang + baris produk), jadi masuk tier sulit. /tambah_kontak setara
/tambah_produk (mudah) DAN strategis: menambah supplier sekarang menyiapkan data
untuk /pengadaan nanti.

## File berubah / baru
- `backend/app/bot/handlers.py` — perintah /tambah_kontak
- `backend/app/bot/parsing.py` — helper parsing kontak (tambahan)
- `backend/app/services/contact_service.py` — service create_contact (BARU)
- `backend/tests/test_bot_parsing.py` — test CI (tambahan)

Tidak ada migrasi / kolom / env baru. Tabel contacts sudah ada.

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/
git commit -m "bot langkah 4: /tambah_kontak"
git push
```
Tonton Railway "Healthcheck succeeded" & CI GitHub hijau (test parsing bertambah).

## Cara pakai
Butuh peran sales atau finance (owner selalu lolos).

### Terpandu
Kirim `/tambah_kontak` polos: pilih tipe (nomor) -> nama -> HP (- untuk kosong)
-> YA.

### Sekali-kirim
```
/tambah_kontak
Tipe: supplier
Nama: PT Sumber Minuman
HP: 081234567890
```
- Tipe & Nama wajib. HP opsional.
- Tipe: customer/pelanggan, supplier/pemasok/vendor, atau keduanya.

## Verifikasi
Bot membalas "Kontak tersimpan: ...". Cek di web Ananta -> menu Kontak
(bisa search nama).

## Berikutnya
- /kasbon (create_loan, jurnal sederhana) — mudah, setara /tambah_pengeluaran.
- /pengadaan, /payment_supplier, /payment_customer — perlu desain "pemilih"
  (cari & pilih supplier/faktur/produk). Tier lebih sulit.
