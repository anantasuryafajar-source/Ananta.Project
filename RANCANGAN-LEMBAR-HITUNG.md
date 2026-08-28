# Rancangan: Lembar Hitung (bagi hasil & komisi bertingkat)

Status: **sudah dikerjakan**. Dokumen ini jadi rujukan rancangan; invarian yang
mengikat ada di `CLAUDE.md` ("Aturan kelima"), dan penjaga eksekusinya
`backend/tests/test_profit_sheet.py`.

Tujuan: menampung kesepakatan bagi hasil yang rumit dan berbeda-beda per
faktur, **tanpa** membiarkan satu pun angka kesepakatan menyentuh Pendapatan,
HPP, atau Persediaan.

---

## 1. Masalah yang diselesaikan

Client punya beberapa bentuk kesepakatan sekaligus atas penjualan yang sama:

- **Andre** — bagi hasil 50% atas selisih harga jual dengan *modal perjanjian*
  (bukan HPP sebenarnya).
- **Bokap Silo & Elias** — komisi persen, tapi dihitung dari **bagian ASF**,
  yaitu sisa profit bersama setelah Andre mengambil bagiannya.
- **Rusdi** — komisi persen dari margin setelah dipotong tarif per dus.

Ketiganya berbeda dasar, berbeda urutan, dan tidak semuanya berlaku di setiap
faktur. Yang sama: semuanya **kesepakatan internal**, dan tidak satu pun boleh
terlihat oleh customer.

### Kenapa tidak ditaruh di faktur

Faktur adalah dokumen yang dilihat customer; harganya harus harga sebenarnya.
Dua jalur kebocoran yang sudah pernah terjadi dan harus terus dijaga:

1. markup diam-diam di `unit_price`, dan
2. komisi dititipkan ke `discount`.

Karena itu lembar hitung hidup di tabelnya sendiri (`profit_sheets`,
`profit_sheet_lines`) dan menempel pada faktur lewat `invoice_id` saja.

---

## 2. Bagian mitra adalah BEBAN, bukan pembagian laba di bawah garis

Ini keputusan yang paling menentukan bentuk jurnalnya, dan paling mudah
salah — jadi diturunkan dari angka client sendiri:

```
omzet                        1.000
HPP riil                     - 600
bagian Andre                 - 150
                             -----
sisa untuk ASF                 250  = hidden margin 100 + bagian ASF 150
```

Angka 250 **hanya keluar kalau 150-nya mengurangi laba**. Kalau bagian Andre
diperlakukan sebagai distribusi laba di bawah garis (mengurangi ekuitas), laba
bersihnya jadi 400 dan tidak pernah cocok dengan apa pun yang dihitung client.

Maka: `Dr 6-1300 Beban Bagi Hasil / Cr 2-1700 Utang Bagi Hasil`.

Konsekuensi yang harus disadari: kalau suatu saat ini benar-benar pembagian
laba pemegang saham, akunnya pindah ke ekuitas dan **laba bersih semua periode
lampau berubah**. Jangan diubah tanpa keputusan client.

---

## 3. Yang dijurnal dan yang tidak

Yang dijurnal hanya **hasil** kesepakatan:

| Baris | Jurnal saat lembar disetujui |
|---|---|
| `jenis = "komisi"` | `Dr 6-1100 Beban Komisi / Cr 2-1600 Utang Komisi` |
| `jenis = "bagi_hasil"` | `Dr 6-1300 Beban Bagi Hasil / Cr 2-1700 Utang Bagi Hasil` |

Yang **tidak pernah** disentuh: Pendapatan (4-1000), HPP (5-1000), Persediaan
(1-1400). Kalau ada yang menambahkan `Line()` ke ketiganya di
`profit_sheet_service`, laba kotor jadi bisa terkontaminasi kesepakatan dan
aturan anti-double-counting client batal — dan itu tidak akan pernah muncul
sebagai error, cuma sebagai angka yang salah.

### Hidden margin tidak dijurnal

`hidden_margin` = `modal_perjanjian − hpp_riil` (100 pada contoh di atas). Ia
**turunan**, bukan pendapatan tersendiri. Menjurnalnya sebagai pendapatan
terpisah membuat laba dobel dan persediaan melenceng. Ia disimpan hanya
sebagai angka tampilan supaya bisa ditelusuri.

---

## 4. Urutan evaluasi: `bagian_asf` selalu terakhir

Ini bagian yang paling berbahaya karena salahnya tetap menghasilkan angka yang
masuk akal.

```
profit_bersama = penjualan − modal_perjanjian        = 1.000 − 700 = 300
bagian mitra   = 50% × profit_bersama                = 150
bagian_asf     = profit_bersama − bagian mitra       = 150
Silo           = 4% × bagian_asf                     = 6
Elias          = 6% × bagian_asf                     = 9
```

Kalau `bagian_asf` dievaluasi **sebelum** baris bagi hasil selesai, ia masih
bernilai 300 dan komisi Silo jadi 12 — dua kali lipat. Angkanya tetap wajar,
jadi tidak akan ketahuan sampai ada yang protes bayarannya.

`profit_sheet_service._evaluasi()` karena itu bekerja dua fase, dan
`FASE_AKHIR` menyebut dasar mana yang wajib ditunda. Dikunci oleh
`test_komisi_pihak_ketiga_dari_bagian_asf_bukan_profit_bersama`.

---

## 5. Daftar dasar TERTUTUP

| Dasar | Rumus |
|---|---|
| `omzet` | penjualan (sebelum PPN) |
| `margin_riil` | penjualan − HPP riil |
| `margin_komisi` | penjualan − HPP dasar komisi |
| `margin_min_pengurang` | penjualan − HPP riil − (pengurang per dus × dus) |
| `profit_bersama` | penjualan − modal perjanjian |
| `bagian_asf` | profit bersama − seluruh bagian mitra |
| `nominal` | angka yang diketik langsung |

`nominal` adalah pintu darurat yang menyimpan **angka**, bukan aturan.

**Custom ≠ user mendefinisikan rumus.** Begitu rumus bisa diketik user, angkanya
berhenti bisa dijelaskan dan tidak bisa dites. Menambah kebutuhan baru berarti
menambah satu entri bernama jelas di `DASAR`, bukan membuka evaluator.

---

## 6. `hpp_riil` dibaca dari jurnal, dan tidak bisa ditimpa

`hpp_riil` di-snapshot dari `journal_entries` milik jurnal faktur, bukan
dihitung ulang dari stok: `avg_cost` sudah bergerak sejak faktur diposting,
jadi menghitung ulang memberi angka berbeda tiap kali lembar dibuka.

Ia juga sengaja **tidak** bisa ditimpa user. Kalau bisa, lembar berhenti bisa
dipakai memeriksa pembukuan. Yang boleh ditimpa `hpp_dasar_komisi` — dan
selisih keduanya ditampilkan berdampingan supaya terlihat.

`jumlah_dus` juga snapshot, dan dihitung **pecahan**: 18 botol dari dus isi 12
= 1,5 dus. Sama dengan `commission_service.persen_margin_min_ongkir`; dua
tempat tidak boleh menjawab berbeda untuk faktur yang sama.

---

## 7. Pengakuan vs pencairan

| Peristiwa | Efek |
|---|---|
| `create_sheet` | draft — tidak menjurnal apa pun |
| `approve_sheet` | beban & utang diakui penuh (Laba Rugi bergerak di sini) |
| `transfer_line` | `Dr Utang / Cr Kas` — **neraca saja** |
| `void_sheet` | jurnal balik atas hak yang belum cair |

Gerbang transfer adalah `invoice.status == "paid"` — **status faktur, bukan
jurnal**. Bebannya sudah diakui sejak lembar disetujui; yang ditahan hanya
uang keluarnya, sampai uang customer benar-benar masuk.

`void_sheet` **wajib** dipakai untuk faktur yang tidak akan pernah lunas. Tanpa
itu, Utang Bagi Hasil & Utang Komisi menumpuk selamanya dengan angka yang tidak
akan pernah dibayar, dan laba terlihat lebih kecil dari kenyataan. Baris yang
sudah ditransfer tidak dibalik — uangnya memang sudah keluar.

---

## 8. Hubungannya dengan modul hak lain

Empat jenis uang keluar, empat titik pengakuan berbeda (lihat "Aturan keenam"
di `CLAUDE.md`):

| Jenis | Diakui kapan | Kode |
|---|---|---|
| Komisi pihak ketiga | lembar disetujui | `profit_sheet_service` |
| Hak mitra | lembar disetujui | `profit_sheet_service` |
| Insentif penjualan | tiap cicilan masuk | `payout_service` |
| Bagi hasil omzet | tutup buku bulanan | `payout_service` |

Yang paling gampang salah: **komisi tidak boleh diakrual ulang per cicilan.**
`approve_sheet` sudah mengakuinya penuh; prorata per cicilan
(`payout_service.porsi_komisi_cair`) hanya menentukan berapa yang boleh
**ditransfer**, dan fungsi itu sengaja murni — tidak membuat jurnal.

Sebaliknya nilai lembar ini menjadi **pengurang** dasar insentif
(`payout_service._pengurang_faktur`): bonus penjualan dihitung dari uang masuk
**bersih**, setelah komisi dan hak mitra atas faktur itu dipotong.

---

## 9. Jaring pengaman

- Total seluruh hak tidak boleh melebihi margin riil faktur. Tanpa ini satu
  digit kelebihan langsung jadi beban besar yang terlihat wajar di jurnal.
- Dasar `profit_bersama` / `bagian_asf` menolak jalan kalau Modal Perjanjian
  belum diisi.
- Satu faktur hanya boleh punya satu lembar aktif; yang berstatus `batal`
  boleh menumpuk.
- Lembar hanya bisa dibuat atas faktur yang sudah diposting — faktur draft
  belum punya HPP di jurnal.
- `void_service.hard_delete_invoice` **menolak** menghapus faktur yang punya
  lembar disetujui, dan mengarahkan orang membatalkan lembarnya dulu supaya
  jurnal baliknya jelas.

---

## 10. Yang masih terbuka

`penjualan` memakai `Invoice.subtotal` (sebelum PPN), sementara gerbang
transfer memakai `Invoice.total` (termasuk PPN) lewat status lunas. Untuk
faktur ber-PPN, margin di lembar karena itu tidak sama dengan uang yang masuk.
Itu disengaja — PPN bukan pendapatan dan tidak boleh ikut dibagi hasil — tapi
belum pernah diuji dengan faktur ber-PPN dari data client.
