# Rancangan: kustomisasi komisi & termin pembayaran

Status: **langkah 1-4 SUDAH dikerjakan** (2026-08-20). Dokumen ini jadi rujukan
rancangan; invarian yang mengikat ada di `CLAUDE.md`.
Tujuan: menampung banyak variasi kesepakatan tanpa mengorbankan ketepatan
Laba Rugi dan Neraca.

---

## 1. Prinsip yang memayungi semuanya

Satu kalimat: **cara membayar tidak boleh menyentuh cara mengakui.**

Setiap kali barang keluar, jurnalnya selalu persis sama, apa pun kesepakatan
pembayarannya:

```
Dr  Piutang Usaha        total faktur
    Cr  Pendapatan Penjualan   subtotal
    Cr  PPN Keluaran            pajak
Dr  HPP                  nilai persediaan keluar
    Cr  Persediaan
```

DP, tempo, tunai, atau "bayar di PO berikutnya" **tidak mengubah satu angka pun
di atas**. Yang berbeda hanya bagaimana piutang itu ditutup kemudian.

Konsekuensi yang membuat rancangan ini layak: Laba Rugi tidak perlu tahu ada
variasi sama sekali. Ia dihitung dari jurnal, jurnalnya seragam, jadi berapa pun
mode pembayaran ditambahkan nanti, PNL tetap benar tanpa disentuh. Semua
kerumitan diisolasi di sisi penyelesaian, yang hanya menyentuh akun neraca.

Aturan ini juga yang menjawab kekhawatiran "banyak kustomisasi tapi harus
akurat": kustomisasinya ditaruh di tempat yang tidak bisa merusak laba.

### Dua hal yang dipisah, di dua sumbu berbeda

| | Menentukan **berapa** | Menentukan **kapan & bagaimana lunas** |
|---|---|---|
| Komisi | skema komisi (§3) | pelunasan komisi (§4) |
| Penjualan | harga di faktur (sudah ada) | termin pembayaran (§5) |

Empat hal ini saling bebas. Menambah tipe komisi baru tidak menyentuh termin;
menambah mode pembayaran tidak menyentuh komisi. Itulah yang mencegah ledakan
kombinasi (3 tipe × 4 termin = 12 kasus kalau digabung, 3 + 4 kalau dipisah).

---

## 2. Perubahan bagan akun (CoA)

Tiga akun baru. Ditambahkan ke `seed_asf.py`, dan untuk database yang sudah
hidup lewat `accounts_map.ensure_account()` (dibuat saat pertama dibutuhkan,
idempoten — pola yang sudah dipakai penyesuaian stok).

| Kode | Nama | Tipe | Untuk |
|---|---|---|---|
| `2-1500` | Uang Muka Pelanggan | liability | DP diterima sebelum barang keluar |
| `2-1600` | Utang Komisi | liability | komisi disepakati tapi belum dibayar |
| `6-1100` | Beban Komisi | expense | **sudah ada**, belum pernah dipakai |

`2-1500` adalah inti dari kerapian neraca. Tanpa akun ini, DP tidak punya
tempat yang benar dan pasti akan diakal-akali jadi sesuatu yang salah.

---

## 3. Sumbu A — skema komisi (menentukan berapa)

### Bentuknya: daftar tertutup, bukan mesin rumus

Tabel baru `commission_schemes`:

| Kolom | Isi |
|---|---|
| `name` | label yang dibaca manusia, mis. "Flat 50rb per faktur" |
| `type` | `nominal` \| `per_botol` \| `persen_margin` \| `persen_omzet` |
| `value` | angkanya: nominal rupiah, tarif per botol, atau persen |
| `default_for_contact_id` | opsional — otomatis dipakai untuk customer ini |
| `default_for_product_id` | opsional — otomatis dipakai untuk produk ini |
| `is_active` | skema lama dinonaktifkan, bukan dihapus |

Empat tipe itu menutup semua kasus yang disebut client:

| Kasus | Tipe | `value` |
|---|---|---|
| "dikasih 50 ribu saja" | `nominal` | 50000 |
| "per botol terjual" | `per_botol` | tarif per botol |
| "5% dari margin" | `persen_margin` | 5 |
| "2% dari omzet" | `persen_omzet` | 2 |

**Kenapa daftar tertutup dan bukan rumus bebas.** Mesin rumus terasa lebih
"powerful" di awal, tapi angkanya berhenti bisa dijelaskan. Enam bulan kemudian
tidak ada yang bisa menjawab kenapa komisi seseorang sekian, karena rumusnya
sudah diubah tiga kali tanpa jejak. Empat tipe tertutup masing-masing hanya
belasan baris kode dan bisa dites satu per satu; menambah tipe kelima nanti
murah. Fleksibilitas yang hilang jauh lebih kecil daripada auditabilitas yang
didapat.

### `per_botol` gratis berkat aturan satuan yang sudah ada

`InvoiceLine.quantity` **selalu** tersimpan dalam botol (aturan dus/botol di
`services/units.py`). Jadi tarif per botol tinggal `quantity × value`, tanpa
konversi apa pun dan tanpa risiko salah 12-48x. Kalau nanti ada "per dus",
turunannya dari `unit_factor` yang sudah di-snapshot per baris.

### Snapshot, bukan referensi

`SalesCommission` menyimpan `scheme_id` **dan** salinan `scheme_type` +
`scheme_value` saat komisi dibuat. Alasannya sama persis dengan `unit_factor`:
kalau tarif per botol naik tahun depan, komisi yang sudah disepakati tahun ini
tidak boleh ikut bergerak. `amount` tetap sumber kebenaran tunggal dan boleh
ditimpa manual — skema hanya mengisinya, tidak mengikatnya.

---

## 4. Sumbu B — pengakuan & pelunasan komisi

### Masalah yang baru disadari: nilainya sering belum diketahui saat faktur terbit

Client menyebut: *"ada komisi yang dibayar setelah faktur muncul, tapi berapa
komisinya kita belum tahu."* Ini menggugurkan rencana sebelumnya untuk mengakui
beban komisi otomatis saat faktur diposting — tidak bisa menjurnal angka yang
belum ada.

**Titik pengakuan yang benar: saat nilainya disepakati**, bukan saat faktur
terbit dan bukan saat dibayar.

```
faktur terbit  ──►  komisi disepakati  ──►  komisi dibayar
   (belum ada         Dr Beban Komisi        Dr Utang Komisi
    jurnal komisi)        Cr Utang Komisi        Cr Kas/Bank
                     ▲ masuk Laba Rugi      ▲ hanya neraca
```

Ini menggeser sedikit dari yang sudah dibangun (sekarang jurnal baru dibuat
saat bayar). Yang berubah cuma kapan jurnal pertama dibuat.

**Kenapa digeser.** Dengan basis kas sekarang, komisi yang sudah disepakati tapi
belum dibayar tidak muncul di mana pun — neraca tidak menunjukkan kewajiban itu,
padahal uangnya pasti keluar. Kalau ada 30 komisi tertunda, laba terlihat lebih
besar dari kenyataan. Begitu ada mode "dibayar di PO berikutnya" yang bisa
berjarak berbulan-bulan, selisihnya jadi material.

**Yang tetap bisa dilihat:** laporan komisi tetap memisahkan kolom "sudah
dibayar" untuk kebutuhan arus kas. Yang berubah hanya di mana bebannya diakui.

> **Disetujui client 2026-08-20 dan sudah diterapkan.** Ini membalik jawaban
> "komisi masuk PNL saat dibayarkan" dari pagi harinya. Komisi lama yang
> terlanjur tercatat tanpa jurnal pengakuan ditambal lewat
> `python -m app.backfill_komisi_akrual`.

### Pelunasan komisi

Setelah diakui, cara melunasi tidak menyentuh Laba Rugi lagi:

| Mode | Jurnal |
|---|---|
| Bayar tunai/transfer | `Dr Utang Komisi / Cr Kas-Bank` |
| Dibayar nanti | (tidak ada — utang menunggu di neraca) |
| Potong dari PO berikutnya | `Dr Utang Komisi / Cr Utang Usaha` |

Mode keempat nanti (mis. potong kasbon karyawan) hanya menambah satu baris di
tabel ini, tanpa menyentuh apa pun yang lain.

---

## 5. Sumbu B' — termin pembayaran customer

### Bentuknya: jadwal termin, bukan satu tanggal jatuh tempo

Sekarang faktur cuma punya `due_date` tunggal dari `Contact.payment_term_days`.
Itu tidak bisa menampung "DP 30% lalu sisanya tempo 30 hari".

Tabel baru `invoice_terms` — satu faktur punya satu atau lebih baris:

| Kolom | Isi |
|---|---|
| `invoice_id` | faktur induk |
| `sequence` | urutan termin (1, 2, ...) |
| `kind` | `tunai` \| `dp` \| `tempo` \| `po_berikutnya` |
| `due_date` | tanggal jatuh tempo — **null** untuk `po_berikutnya` |
| `amount` | nominal termin ini |
| `settled_amount` | sudah tertutup berapa |

**Invarian yang wajib ditegakkan:** `SUM(amount) == invoice.total`. Ditolak di
service kalau tidak sama, sama tegasnya dengan debit==kredit di `post_journal`.
Tanpa ini, jadwal dan faktur bisa berbeda diam-diam dan AR Aging jadi bohong.

Empat mode client memetakan langsung:

| Kesepakatan | Jadwal |
|---|---|
| Bayar sekarang | 1 baris `tunai`, jatuh tempo hari ini |
| Tempo 30 hari | 1 baris `tempo`, +30 hari |
| DP 30% lalu tempo | 2 baris: `dp` + `tempo` |
| Bayar di PO berikutnya | 1 baris `po_berikutnya`, tanpa tanggal |

Kombinasi yang belum disebut client pun sudah tertampung tanpa kode baru —
itu gunanya membuat jadwal alih-alih daftar mode.

### DP / uang muka: satu-satunya bagian yang bisa merusak neraca

Uang masuk **sebelum** barang keluar bukan pendapatan. Saat itu ASF berhutang
barang, bukan menerima penghasilan. Tabel baru `customer_advances`, dan alurnya
tiga langkah:

```
1. Terima DP (belum ada faktur)
   Dr  Kas/Bank                  1.000.000
       Cr  Uang Muka Pelanggan       1.000.000     ← liability, bukan pendapatan

2. Faktur terbit (jurnal normal, tidak tahu-menahu soal DP)
   Dr  Piutang Usaha             3.000.000
       Cr  Pendapatan / PPN          3.000.000
   Dr  HPP / Cr Persediaan

3. Alokasi DP ke faktur
   Dr  Uang Muka Pelanggan       1.000.000
       Cr  Piutang Usaha             1.000.000     ← sisa piutang 2.000.000
```

**PPN atas DP: default TIDAK dipungut** (keputusan client 2026-08-20). Langkah 1
murni kas lawan liability. Kalau suatu saat perlu, ditambahkan sebagai flag per
perusahaan — bukan hardcode — dan hanya menyentuh langkah 1.

Dua hal yang harus dijaga di implementasi:

- **Sisa DP tetap liability.** Kalau DP lebih besar dari faktur, kelebihannya
  tinggal di `2-1500` sebagai saldo uang muka customer, siap dipakai faktur
  berikutnya. Jangan pernah dibiarkan menjadi piutang negatif — itu yang membuat
  neraca terlihat aneh dan AR Aging kacau.
- **DP tidak boleh lewat `receive_payment`.** Fungsi itu selalu mengkredit
  Piutang Usaha. Kalau dipakai untuk DP atas faktur draft, piutang jadi minus
  dan pendapatan belum ada lawannya. Harus jalur terpisah.

### "Bayar di PO berikutnya" bukan mode pembayaran

Piutangnya biasa saja dan sudah benar. Yang salah hanya laporannya: `ar_aging`
sekarang memakai `inv.due_date or inv.date` sebagai acuan umur, jadi kesepakatan
"tagih nanti saat order berikutnya" akan dihitung menunggak 90+ hari padahal itu
memang yang disepakati. Perlu jenis termin eksplisit supaya laporan piutang
tidak menyesatkan orang yang menagih.

---

## 6. Dampak ke laporan

| Laporan | Perubahan |
|---|---|
| Laba Rugi | **tidak ada** — jurnal penjualan tetap seragam. Beban Komisi akhirnya terisi. |
| Neraca | dua akun baru muncul: Uang Muka Pelanggan, Utang Komisi. Keduanya kewajiban yang selama ini tidak terlihat. |
| AR Aging | dibaca dari `invoice_terms`, bukan `invoice.due_date`. Termin `po_berikutnya` masuk kolom terpisah "tanpa jatuh tempo", tidak dihitung menunggak. |
| Laporan komisi | kolom "diakui" dan "dibayar" dipisah; hanya yang diakui yang cocok dengan akun 6-1100. |

### Tes penjaga yang harus ikut dibuat

Mengikuti pola `test_valuasi_stok_cocok_dengan_saldo_persediaan_di_jurnal` yang
sudah ada — laporan harus cocok dengan jurnal, bukan sekadar tidak error:

1. `test_saldo_piutang_cocok_dengan_neraca` — total outstanding semua faktur ==
   saldo akun `1-1200` di neraca. Ini yang menangkap kalau DP salah jalur.
2. `test_jumlah_termin_sama_dengan_total_faktur` — invarian jadwal.
3. `test_dp_tidak_menyentuh_pendapatan` — akun `4-1000` nol sampai faktur terbit.
4. `test_sisa_dp_tidak_jadi_piutang_negatif`.
5. `test_po_berikutnya_tidak_dihitung_menunggak` di AR Aging.

---

## 7. Apa yang diotomatiskan, apa yang tidak

**Otomatis, aman:**
- menghitung nilai komisi dari skema begitu faktur diposting → jadi **draft**
- membuat jadwal termin dari template kesepakatan customer
- mengingatkan termin jatuh tempo & komisi belum dibayar
- menawarkan alokasi DP yang tersisa saat faktur baru dibuat untuk customer itu
- menawarkan potongan komisi saat PO baru ke pihak yang sama
- semua laporan

**Jangan pernah otomatis:** memposting uang keluar atau menutup piutang tanpa
konfirmasi manusia. Ini prinsip yang sudah disepakati di modul OCR (foto →
draft → approve → ledger); terapkan sama di sini. Otomasi yang mengeluarkan
uang sendiri adalah otomasi yang paling mahal ketika salah.

**Jangan pernah dibuat bisa diatur dari halaman Pengaturan:** rumus jurnal,
pemetaan akun, urutan pengakuan. Yang boleh diatur user hanya angka dan pilihan
dari daftar tertutup.

---

## 8. Urutan pengerjaan

Tiap langkah berdiri sendiri dan bisa dideploy tanpa menunggu langkah berikutnya.

| # | Isi | Menyentuh jurnal? | Perlu keputusan client? |
|---|---|---|---|
| 1 | Skema komisi (§3) | tidak | tidak |
| 2 | Akun `2-1500` + uang muka/DP (§5) | ya, jalur baru | tidak (PPN sudah diputus) |
| 3 | Jadwal termin + AR Aging (§5, §6) | tidak | tidak |
| 4 | Akrual komisi (§4) | ya, mengubah yang ada | ✅ disetujui |

Langkah 1 murni tambahan dan langsung menyelesaikan "flat 50 ribu" dan "per
botol". Langkah 2 yang paling mendesak untuk kerapian neraca. Langkah 4 ditaruh
terakhir karena satu-satunya yang membalik keputusan sebelumnya.

Migrasi: semua tabel baru, tidak ada kolom lama yang berubah tipe. Faktur lama
tanpa `invoice_terms` diperlakukan sebagai satu termin `tempo` dengan
`due_date` yang sudah ada — jadi tidak ada backfill yang bisa menggeser angka.

---

## 9. Yang masih terbuka

1. **PPN atas DP** — diputus tidak ada; disiapkan sebagai flag kalau berubah.
2. **Penerima komisi** masih teks bebas. Kalau nanti perlu laporan per-orang yang
   rapi, butuh master penerima. Belum mendesak.
3. `reports_ext.commission` & `gpm` memakai modal ACUAN dari master, sementara
   HPP di Laba Rugi memakai `avg_cost` nyata. Sudah dilabeli "Simulasi"; belum
   diselaraskan dan sebaiknya jangan diselaraskan sepihak.
