# Riwayat pengembangan

Arsip catatan langkah pengembangan lama. **Bukan dokumentasi yang berlaku** —
isinya menggambarkan keadaan kode pada saat catatan itu ditulis, bukan keadaan
sekarang. Untuk panduan yang berlaku, pakai berkas di root repo:

| Berkas | Isi |
|---|---|
| `README.md` | pengantar proyek |
| `CLAUDE.md` | arsitektur & aturan invarian (jurnal, satuan dus/botol) |
| `DEPLOY.md` | langkah deploy |
| `TUTORIAL.md` | panduan pemakaian |
| `STATUS.md` | status pekerjaan |

Catatan di sini disimpan karena beberapa masih menjelaskan ALASAN sebuah
setelan dipilih — terutama berkas profiling, yang menerangkan mengapa nilai
bawaan `PROFILING_SEARCH_CONTEXT_SIZE` dan `PROFILING_OPENAI_MAX_RETRIES`
sengaja dibuat konservatif. Kalau sebuah catatan bertentangan dengan kode,
kode yang benar.

## Isi

### Bot Telegram
`README-BOT-STEP1` … `STEP11` — catatan per langkah pembangunan bot: multiuser,
pengeluaran, kontak, kasbon, bayar, pengadaan, jual, report, insight.
`README-BOT-FIX-BLOK` — perbaikan parsing blok perintah.

### Lapisan AI
`README-AI-AGENT-OPENAI`, `README-AI-GPT-FIX` — agent OpenAI & perbaikan GPT.

### Profiling
`CHANGES_PROFILING_*` — ringkasan perubahan.
`PROFILING_*_SETUP` — langkah penyiapan.
