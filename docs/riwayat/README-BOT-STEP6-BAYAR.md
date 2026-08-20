# Bot langkah 6 — /bayar_supplier & /bayar_customer (by nomor faktur)

Dua perintah pembayaran, tanpa "pemilih" rumit: pengguna menyebut NOMOR faktur,
bot mencarinya lalu memposting jurnal lewat service Ananta (pay_bill /
receive_payment).

## File berubah
- `backend/app/bot/handlers.py` — /bayar_supplier, /bayar_customer
- `backend/app/bot/parsing.py` — parse_payment_block (tambahan)
- `backend/tests/test_bot_parsing.py` — test CI (tambahan)

Tidak ada migrasi / kolom / env baru.

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/
git commit -m "bot langkah 6: bayar supplier & customer by nomor faktur"
git push
```
Tonton Railway "Healthcheck succeeded" & CI GitHub hijau.

## Cara pakai
Butuh peran finance (owner selalu lolos).

### /bayar_supplier (bayar faktur pembelian)
Terpandu: nomor faktur (BILL/...) -> bot tampilkan sisa tagihan -> jumlah -> YA.
Sekali-kirim:
```
/bayar_supplier
Faktur: BILL/2026/0001
Jumlah: 500000
```

### /bayar_customer (terima pembayaran faktur penjualan)
Terpandu: nomor faktur (INV/...) -> sisa -> jumlah -> YA.
Sekali-kirim:
```
/bayar_customer
Faktur: INV/2026/0001
Jumlah: 500000
```

## Batasan v1 (jujur)
- Sumber/tujuan kas = Kas (1-1000) saja. Pembayaran via BCA/OCBC lewat web dulu;
  bisa ditambah nanti (perlu resolver kode akun -> id).
- Pengguna perlu tahu NOMOR faktur (terlihat di web; nanti juga di balasan
  /pengadaan). Ini sengaja: menghindari "pemilih" inline-keyboard yang jauh
  lebih kompleks. Bila daftar faktur jadi banyak & merepotkan, pemilih
  berbasis pencarian bisa dibangun kemudian.

## Verifikasi
Bot membalas nomor pembayaran. Cek web Ananta -> menu Pembayaran, dan Buku Besar
(supplier: Dr Utang / Cr Kas; customer: Dr Kas / Cr Piutang).

## Tersisa dari Bagian 3 spec
- /pengadaan (faktur pembelian dgn baris produk) — tier paling sulit; rencana:
  format sekali-kirim dengan SKU + nama supplier/gudang, atau pemilih.
- /input_transaksi (omzet lempar/collect) — paling kompleks, ditunda.
