# Status implementasi — disesuaikan untuk PT ASF

## ✅ Sudah jalan (end-to-end)
- **Fondasi:** monorepo Next.js + FastAPI, design tokens "Calm Ledger", app-shell.
- **Auth & RBAC:** login JWT (Argon2), peran owner/finance/sales/warehouse/viewer,
  `require_roles` dicek di backend.
- **Master data ASF (seed dari Excel):** `app/seed_asf.py`
  - CoA disesuaikan ke akun riil ASF (Beban Ekspedisi, Komisi, Investor, Entertainment,
    Perawatan Kendaraan, **Piutang Tidak Tertagih**, dll) + akun bank Silo.
  - 18 produk dengan modal & harga jual nyata (dari sheet KOMISI).
  - 54 customer hasil ekstraksi dari sheet penjualan; supplier contoh.
- **Akuntansi inti (jurnal = sumber kebenaran tunggal):**
  - `services/journal.py` — invarian **debit=kredit** (ditest).
  - `services/invoice_service.py` — **penjualan -> jurnal (Piutang/Pendapatan/PPN +
    HPP/Persediaan) -> potong stok**, atomik.
  - `services/purchase_service.py` — **pembelian/pengadaan -> jurnal (Persediaan/PPN
    Masukan/Utang) -> stok MASUK + update average cost**, atomik. *(modul baru)*
  - `services/payment_service.py` — pelunasan piutang (terima) & utang (bayar) -> jurnal. *(baru)*
- **Laporan (diturunkan dari jurnal):** `services/reports.py` *(baru)*
  - Laba Rugi, Neraca, Neraca Saldo, **AR Aging** (bucket umur), Valuasi Stok.
  - Endpoint: `/api/v1/reports/{profit-loss,balance-sheet,trial-balance,ar-aging,stock-valuation}`.
- **Dashboard:** pendapatan, piutang, **utang, nilai persediaan**.
- **Frontend:** halaman Dashboard, Penjualan, Pembelian, Produk & Stok, Kontak,
  **Laporan** (Laba Rugi + grafik, AR Aging, Valuasi Stok), + stub Kas & Bank/Akuntansi/Pengaturan.
- **Test:** `test_journal_balance.py`, `test_invoice_posting.py`, **`test_bill_posting.py`** (average cost).

## 🟡 Lanjutan (pola sudah ada)
- Form input penjualan/pembelian di UI (API sudah jalan, tinggal sambungkan form).
- Modul khas ASF: komisi per-sales per-SKU, bagi hasil investor & dividen (Silo/Abay/Fei/Ido).
- Migrasi saldo awal & data historis 2 tahun dari `ASF_MASTER_DATA.xlsx`.
- Ekspor laporan PDF/Excel, jurnal penyesuaian, tutup buku, multi-gudang transfer, FIFO.
- e-Faktur/Coretax, ringkasan PPN/PPh.

## Cara melanjutkan
Pola "transaksi -> jurnal otomatis + mutasi" dicontohkan penuh di
`invoice_service.py` (keluar) dan `purchase_service.py` (masuk). Modul baru tinggal
mengikuti: hitung total -> `post_journal()` -> update stok/saldo -> `commit()` (rollback bila gagal).

## Jalankan
Backend: `python -m app.seed_asf` (seed PT ASF) lalu `uvicorn app.main:app --reload`.
Frontend: `npm install && npm run dev`. Login: admin@ananta.local / admin12345.
