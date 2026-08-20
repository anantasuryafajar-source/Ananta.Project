# Bot langkah 10 — /report & /omzet (sisi baca)

Menambah dua perintah BACA (tanpa menulis apa pun). Melengkapi Bagian 3 spec.

## File berubah
- backend/app/bot/handlers.py — perintah /report & /omzet

Tidak ada migrasi / kolom / env / dependency baru. Memakai fungsi laporan yang
sudah ada (reports_ext.cashflow & reports_ext.sales_kpi).

## Deploy (PowerShell, dari root repo)
```powershell
git add backend/app/bot/handlers.py
git commit -m "bot langkah 10: /report & /omzet (sisi baca)"
git push
```
Tonton Railway "Healthcheck succeeded" & CI hijau.

## Cara pakai (butuh peran finance/viewer; owner lolos)

### /omzet  -> Omzet Lempar vs Collect (bulan berjalan)
Contoh balasan:
  Omzet 01 Jul - 05 Jul 2026
  Lempar (faktur terbit) : Rp12.500.000
  Collect (terbayar)     : Rp8.000.000
  Rasio collect          : 64%
  Belum tertagih         : Rp4.500.000

- Lempar = total nilai faktur penjualan bulan ini (sales_kpi.omzet).
- Collect = bagian yang sudah dibayar dari faktur tsb (sales_kpi.paid).

### /report -> ringkasan likuiditas (90 hari terakhir)
Contoh balasan:
  Laporan Likuiditas (90 hari terakhir)
  Kas masuk         : Rp...
  Kas keluar        : Rp...
  Arus kas bersih   : Rp...
  Saldo kas & bank  : Rp...
  Burn rate/bulan   : Rp...        (hanya bila arus kas negatif)
  Cash runway       : ~X bulan     (saldo kas / burn rate)

Definisi:
- Arus kas = mutasi jurnal akun Kas/Bank (1-10xx/1-11xx) 90 hari terakhir.
- Saldo kas & bank = akumulasi seluruh mutasi Kas/Bank s/d hari ini.
- Burn rate = rata-rata arus kas bersih negatif per bulan. Bila arus kas positif,
  tidak ada burn.
- Cash runway = saldo kas / burn rate (perkiraan berapa bulan kas bertahan).

## Catatan jujur
- Angka /report bergantung pada saldo awal & jurnal Kas/Bank yang sudah terisi.
  Bila saldo awal belum di-import (Neraca belum lengkap), "Saldo kas & bank" bisa
  meleset dan runway tak dapat dihitung (sudah ditangani: pesan aman, bukan error).
- Kedua perintah READ-ONLY: tidak menulis/mengubah data.
- Belum diuji terhadap data sungguhan di lingkungan build (jaringan mati); yang
  dipastikan: compile, signature laporan cocok, formatter teruji. Uji nyata:
  kirim /omzet & /report setelah deploy.

## Status Bagian 3 spec
SELESAI penuh: seluruh perintah tulis + baca (/report, /omzet) kini ada.
