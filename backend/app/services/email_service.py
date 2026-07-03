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


def reset_email_html(full_name: str, reset_url: str,
                     company_name: str = "PT ASF",
                     company_address: str = "") -> str:
    tmpl = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Atur ulang kata sandi</title></head>
<body style="margin:0;padding:0;background:#F6F8F6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F8F6;">
<tr><td align="center" style="padding:32px 16px;">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:#FFFFFF;border:1px solid #E4E8E4;border-radius:12px;overflow:hidden;">
    <tr><td style="height:4px;background:#E2A33C;font-size:0;line-height:0;">&nbsp;</td></tr>
    <tr><td style="background:#2F6F5E;padding:22px 32px;"><span style="font:700 24px/1 'Hanken Grotesk',Arial,sans-serif;color:#FFFFFF;letter-spacing:-0.3px;">Ananta</span></td></tr>
    <tr><td style="padding:32px 32px 8px;font-family:Arial,sans-serif;">
      <p style="margin:0 0 6px;font-size:18px;font-weight:bold;color:#1B2A26;">Atur ulang kata sandi</p>
      <p style="margin:0;font-size:14px;color:#5C6B65;line-height:1.7;">Halo {{nama}}, kami menerima permintaan untuk mengatur ulang kata sandi akunmu. Klik tombol di bawah untuk membuat kata sandi baru.</p>
    </td></tr>
    <tr><td align="center" style="padding:24px 32px 8px;">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr><td bgcolor="#2F6F5E" style="border-radius:8px;">
        <a href="{{link_reset}}" style="display:inline-block;padding:13px 40px;font:bold 15px Arial,sans-serif;color:#FFFFFF;text-decoration:none;border-radius:8px;">Buat kata sandi baru</a>
      </td></tr></table>
    </td></tr>
    <tr><td style="padding:16px 32px;font-family:Arial,sans-serif;">
      <p style="margin:0;font-size:12px;color:#8A958F;text-align:center;line-height:1.7;">Tautan ini berlaku {{masa_berlaku}}. Jika kamu tidak meminta ini, abaikan saja email ini — kata sandimu tetap aman.</p>
    </td></tr>
    <tr><td style="padding:0 32px 28px;font-family:Arial,sans-serif;">
      <p style="margin:0;font-size:11px;color:#8A958F;line-height:1.6;word-break:break-all;">Tombol tidak berfungsi? Salin tautan ini:<br><span style="color:#5C6B65;">{{link_reset}}</span></p>
    </td></tr>
    <tr><td style="background:#F6F8F6;padding:20px 32px;border-top:1px solid #E4E8E4;font-family:Arial,sans-serif;"><p style="margin:0;font-size:12px;color:#8A958F;line-height:1.6;">{{nama_perusahaan}} · {{alamat_perusahaan}}<br>Email ini dikirim otomatis oleh Ananta.</p></td></tr>
  </table>
</td></tr></table>
</body></html>
"""
    return (tmpl
            .replace("{{nama}}", full_name or "")
            .replace("{{link_reset}}", reset_url)
            .replace("{{masa_berlaku}}", "1 jam")
            .replace("{{nama_perusahaan}}", company_name)
            .replace("{{alamat_perusahaan}}", company_address))
