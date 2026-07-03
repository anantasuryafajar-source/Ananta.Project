"""Pengiriman email via Resend. Dipakai untuk reset kata sandi.

Aman-gagal: bila RESEND_API_KEY belum diisi atau Resend menolak, fungsi
mengembalikan (False, pesan) tanpa melempar — supaya alur tetap jalan dan
tidak membocorkan apakah email terdaftar.
"""
from __future__ import annotations
import httpx
from ..core.config import settings

RESEND_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> tuple[bool, str]:
    if not settings.RESEND_API_KEY:
        return False, "RESEND_API_KEY belum diatur."
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={"from": settings.EMAIL_FROM, "to": [to],
                      "subject": subject, "html": html},
            )
        if r.status_code >= 400:
            return False, f"Resend error {r.status_code}: {r.text[:200]}"
        return True, "terkirim"
    except Exception as e:  # jaringan dsb — jangan sampai menggagalkan request
        return False, f"gagal kirim: {e}"


def reset_email_html(full_name: str, reset_url: str) -> str:
    return f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#1f2a26">
  <h2 style="color:#2F6F5E;margin-bottom:4px">Ananta</h2>
  <p>Halo {full_name or ''},</p>
  <p>Kami menerima permintaan untuk mengatur ulang kata sandi akun Anda.
     Klik tombol di bawah untuk membuat kata sandi baru. Tautan berlaku 1 jam.</p>
  <p style="text-align:center;margin:28px 0">
    <a href="{reset_url}" style="background:#2F6F5E;color:#fff;text-decoration:none;
       padding:12px 24px;border-radius:8px;display:inline-block">Atur Ulang Kata Sandi</a>
  </p>
  <p style="font-size:12px;color:#5c6b64">Jika Anda tidak meminta ini, abaikan email ini —
     kata sandi Anda tetap aman.</p>
  <p style="font-size:12px;color:#5c6b64">Atau salin tautan ini: <br>{reset_url}</p>
</div>"""
