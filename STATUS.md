# Status implementasi

## ✅ Sudah jalan (end-to-end siap setelah install)
- **Fondasi:** monorepo, design tokens "Calm Ledger" (Tailwind v4 + dark scaffold),
  app-shell (sidebar, topbar, signature continuity-ribbon), font lokal next/font.
- **Auth & RBAC:** login (JWT access+refresh, Argon2), `/auth/me`, `require_roles`
  dicek di backend. Peran: owner/finance/sales/warehouse/viewer.
- **Master data (API):** Kontak (list+create), Produk (list+create), CoA (list).
- **Akuntansi inti:**
  - `services/journal.py` — posting jurnal dengan invarian **debit=kredit** (ditest).
  - `services/numbering.py` — penomoran dokumen otomatis + reset periode (row-lock).
  - `services/invoice_service.py` — **terbit faktur → jurnal otomatis (Piutang/
    Pendapatan/PPN Keluaran + HPP/Persediaan) → potong stok**, atomik dalam satu
    transaksi DB. Ditest (balance + stok berkurang).
- **Dashboard:** ringkasan pendapatan bulan ini + total piutang (API + UI).
- **Seed:** CoA standar Indonesia, 5 peran, gudang default, user admin.
- **Test:** `test_journal_balance.py`, `test_invoice_posting.py`.

## 🟡 Scaffold / pola sudah ada, tinggal dilanjutkan
- Penjualan: Penawaran → SO (model invoice sudah ada; tambah quotation/SO + konversi).
- Pembelian: PO → Bill → Pembayaran + HPP masuk (cermin dari invoice_service).
- Kas & Bank, rekonsiliasi, transfer dana.
- Buku Besar, Neraca Saldo, jurnal penyesuaian, tutup buku.
- Laporan (Laba Rugi/Neraca/Arus Kas) + ekspor PDF/Excel/CSV.
- Pajak lanjutan (PPh, ringkasan PPN, struktur e-Faktur/Coretax).
- Stok opname, multi-gudang transfer, FIFO (sekarang Average jalan).
- Command palette (Ctrl/Cmd+K), dark-mode toggle, audit log UI, TanStack Query/Table.

## Cara melanjutkan tiap modul
Pola "transaksi → jurnal otomatis + mutasi" sudah dicontohkan penuh di
`invoice_service.py`. Modul Pembelian/Pembayaran mengikuti pola yang sama:
hitung total → `post_journal()` dengan baris debit/kredit yang sesuai → update
stok/saldo → `commit()` (rollback bila gagal). Tambah router + schema serupa
contoh yang ada.
