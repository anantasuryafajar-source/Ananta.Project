"""Handler perintah bot Telegram (langkah 1).

Semua tulisan ke database mengalir lewat service Ananta yang sudah tervalidasi.
Identitas & RBAC memakai tabel/logika Ananta yang sudah ada — bot tidak punya
hak istimewa sendiri.
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from ..core.config import settings
from ..core.database import SessionLocal
from ..deps import user_roles
from ..models import Role, TelegramLink, User, UserRole, Bill, Invoice, Contact, Product, Warehouse
from ..services.product_service import create_product
from ..services.contact_service import create_contact
from ..services.expense_service import create_expense
from ..services.expense_service import create_loan
from ..services.payment_service import pay_bill, receive_payment
from ..services.purchase_service import create_and_post_bill
from ..services.journal import JournalNotBalanced
from .parsing import (
    CONTACT_TYPES,
    DEFAULT_EXPENSE_CODE,
    DEFAULT_PAID_CODE,
    EXPENSE_ACCOUNTS,
    PAYMENT_ACCOUNTS,
    parse_amount,
    parse_contact_block,
    parse_expense_block,
    parse_item_line,
    parse_loan_block,
    parse_payment_block,
    parse_pengadaan_block,
    resolve_contact_type,
    resolve_expense_account,
    resolve_payment_account,
)
from .state import clear_state, load_state, set_state

# Peran yang boleh menambah produk (owner selalu lolos).
PRODUCT_ROLES = {"warehouse", "finance", "sales"}
EXPENSE_ROLES = {"finance"}
CONTACT_ROLES = {"sales", "finance"}
KASBON_ROLES = {"finance"}
PAYMENT_ROLES = {"finance"}
PENGADAAN_ROLES = {"warehouse", "finance"}

PENGADAAN_HINT = (
    "Format:\n/pengadaan\n"
    "Supplier: PT Sumber Minuman\n"
    "Gudang: Gudang Utama   (opsional)\n"
    "Item: MNS-WHK x 10 @ 250000\n"
    "Item: CLA-AZL x 5 @ 800000\n\n"
    "Tiap Item: SKU x jumlah @ harga_beli. Boleh banyak baris Item."
)

PAY_SUPPLIER_HINT = (
    "Format cepat:\n/bayar_supplier\nFaktur: BILL/2026/0001\nJumlah: 500000"
)
PAY_CUSTOMER_HINT = (
    "Format cepat:\n/bayar_customer\nFaktur: INV/2026/0001\nJumlah: 500000"
)

KASBON_FORMAT_HINT = (
    "Format cepat (kirim sekaligus):\n"
    "/kasbon\n"
    "Nama: Budi\n"
    "Jumlah: 500000\n"
    "Bayar: kas"
)

CONTACT_FORMAT_HINT = (
    "Format cepat (kirim sekaligus):\n"
    "/tambah_kontak\n"
    "Tipe: supplier\n"
    "Nama: PT Sumber Minuman\n"
    "HP: 081234567890"
)

# Contoh format sekali-kirim untuk /tambah_pengeluaran.
EXPENSE_FORMAT_HINT = (
    "Format cepat (kirim sekaligus):\n"
    "/tambah_pengeluaran\n"
    "Jumlah: 150000\n"
    "Untuk: Bensin operasional\n"
    "Beban: bensin\n"
    "Bayar: kas"
)


def _menu(title: str, items) -> str:
    lines = [title]
    for i, (_code, label) in enumerate(items, 1):
        lines.append(f"{i}. {label}")
    return "\n".join(lines)


def _pick_index(text: str, n: int):
    t = (text or "").strip()
    if not t.isdigit():
        return None
    i = int(t)
    return i - 1 if 1 <= i <= n else None

# Contoh format sekali-kirim untuk /tambah_produk.
PRODUCT_FORMAT_HINT = (
    "Format cepat (kirim sekaligus):\n"
    "/tambah_produk\n"
    "SKU: EBN\n"
    "Nama: MINUMAN EBEN\n"
    "Satuan: botol\n"
    "Harga: 0"
)


def _parse_price(text: str):
    """Ubah teks harga jadi Decimal. Kembalikan None bila tidak valid."""
    cleaned = (text or "").replace(".", "").replace(",", "").replace(" ", "").strip()
    if cleaned == "":
        return Decimal("0")
    try:
        price = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if price < 0:
        return None
    return price


def parse_product_block(block: str) -> dict:
    """Parse blok multi-baris 'Kunci: Nilai' jadi dict field produk.

    Toleran: tanda '-' di depan, spasi bebas, kunci Indonesia/Inggris.
    """
    out: dict = {}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "sku":
            out["sku"] = val[:40]
        elif key in ("nama", "name"):
            out["name"] = val[:200]
        elif key in ("satuan", "unit"):
            out["unit"] = val[:20]
        elif key in ("harga", "harga jual", "price"):
            out["price_raw"] = val
    return out


def _code_valid(target) -> bool:
    """True bila kode tautan user masih ada dan belum kedaluwarsa."""
    exp = target.telegram_link_expires
    if exp is None:
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > datetime.now(timezone.utc)


async def _linked_user(db, chat_id: int) -> User | None:
    link = (
        await db.execute(
            select(TelegramLink).where(
                TelegramLink.telegram_chat_id == chat_id,
                TelegramLink.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if link is None:
        return None
    return (
        await db.execute(select(User).where(User.id == link.user_id))
    ).scalar_one_or_none()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Halo! Ini bot Ananta.\n\n"
        "1. Ketik /link untuk menautkan akun.\n"
        "2. Ketik /tambah_produk untuk menambah produk.\n"
        "Ketik /bantuan untuk daftar perintah."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Perintah tersedia:\n"
        "/link <kode> - tautkan akun Telegram ke Ananta\n"
        "/buat_kode <email> - (owner) buat kode tautan untuk pengguna\n"
        "/tambah_produk - tambah produk baru (terpandu atau sekali-kirim)\n"
        "/tambah_pengeluaran - catat pengeluaran (terpandu atau sekali-kirim)\n"
        "/tambah_kontak - tambah customer/supplier (terpandu atau sekali-kirim)\n"
        "/kasbon - catat kasbon karyawan (terpandu atau sekali-kirim)\n"
        "/bayar_supplier - bayar faktur pembelian (by nomor)\n"
        "/bayar_customer - terima pembayaran faktur penjualan (by nomor)\n"
        "/pengadaan - faktur pembelian dari supplier (SKU x qty @ harga)\n"
        "/batal - batalkan input yang sedang berjalan\n"
        "/bantuan - tampilkan bantuan ini\n\n"
        + PRODUCT_FORMAT_HINT
    )


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args = context.args or []
    code = args[0].strip() if args else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is not None:
            await update.message.reply_text(f"Akun ini sudah tertaut sebagai {u.email}.")
            return

        # --- Mode kode: /link <kode> (untuk semua pengguna) ---
        if code:
            target = (
                await db.execute(
                    select(User).where(
                        User.telegram_link_code == code,
                        User.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if target is None or not _code_valid(target):
                await update.message.reply_text(
                    "Kode tidak valid atau sudah kedaluwarsa. Minta kode baru ke owner."
                )
                return
            # tautkan chat ini ke user tsb (perbarui bila chat pernah tertaut)
            existing = (
                await db.execute(
                    select(TelegramLink).where(
                        TelegramLink.telegram_chat_id == chat_id
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    TelegramLink(
                        telegram_chat_id=chat_id, user_id=target.id, is_active=True
                    )
                )
            else:
                existing.user_id = target.id
                existing.is_active = True
            # kode sekali-pakai: hapus setelah dipakai
            target.telegram_link_code = None
            target.telegram_link_expires = None
            await db.commit()
            await update.message.reply_text(
                f"Berhasil tertaut sebagai {target.email}."
            )
            return

        # --- Bootstrap owner via TELEGRAM_OWNER_CHAT_ID (tanpa kode) ---
        owner_chat = str(settings.TELEGRAM_OWNER_CHAT_ID or "").strip()
        if owner_chat and str(chat_id) == owner_chat:
            owner_user = (
                await db.execute(
                    select(User)
                    .join(UserRole, UserRole.user_id == User.id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(Role.name == "owner")
                )
            ).scalars().first()
            if owner_user is None:
                await update.message.reply_text(
                    "Tidak menemukan akun owner di sistem. Hubungi developer."
                )
                return
            db.add(
                TelegramLink(
                    telegram_chat_id=chat_id, user_id=owner_user.id, is_active=True
                )
            )
            await db.commit()
            await update.message.reply_text(
                f"Berhasil tertaut sebagai {owner_user.email} (owner)."
            )
        else:
            await update.message.reply_text(
                "Untuk menautkan akun, minta KODE ke owner, lalu kirim:\n"
                "/link <kode>\n\n"
                f"Chat ID kamu: {chat_id}"
            )


async def cmd_buat_kode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner membuat kode tautan sekali-pakai untuk seorang pengguna (by email)."""
    chat_id = update.effective_chat.id
    args = context.args or []
    email = args[0].strip().lower() if args else ""

    async with SessionLocal() as db:
        owner = await _linked_user(db, chat_id)
        if owner is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, owner.id)
        if "owner" not in roles:
            await update.message.reply_text("Hanya owner yang bisa membuat kode tautan.")
            return
        if not email:
            await update.message.reply_text(
                "Format: /buat_kode <email-pengguna>\n"
                "Contoh: /buat_kode abay@anantaasf.com\n\n"
                "Pengguna harus sudah punya akun di Ananta (menu pengelolaan pengguna)."
            )
            return

        target = (
            await db.execute(
                select(User).where(
                    func.lower(User.email) == email,
                    User.company_id == owner.company_id,
                )
            )
        ).scalar_one_or_none()
        if target is None:
            await update.message.reply_text(
                f"Belum ada pengguna dengan email {email}. Buat akunnya dulu di Ananta, "
                "lalu jalankan perintah ini lagi."
            )
            return

        new_code = secrets.token_urlsafe(6)
        target.telegram_link_code = new_code
        target.telegram_link_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.commit()
        await update.message.reply_text(
            f"Kode tautan untuk {target.email} (berlaku 24 jam):\n\n"
            f"{new_code}\n\n"
            "Kirim kode ini ke orangnya. Mereka membuka bot lalu mengetik:\n"
            f"/link {new_code}"
        )


async def cmd_batal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    async with SessionLocal() as db:
        await clear_state(db, chat_id)
    await update.message.reply_text("Dibatalkan.")


async def cmd_tambah_produk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    # Pisahkan token perintah dari sisa pesan (bisa multi-baris).
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(PRODUCT_ROLES):
            await update.message.reply_text("Kamu tidak punya akses menambah produk.")
            return

        # --- Mode sekali-kirim: ada blok format di bawah perintah ---
        if body:
            fields = parse_product_block(body)
            missing = [k for k in ("sku", "name") if not fields.get(k)]
            if missing:
                label = {"sku": "SKU", "name": "Nama"}
                await update.message.reply_text(
                    "Format kurang lengkap. Wajib ada "
                    + " dan ".join(label[m] for m in missing)
                    + ".\n\n"
                    + PRODUCT_FORMAT_HINT
                )
                return
            price = _parse_price(fields.get("price_raw", "0"))
            if price is None:
                await update.message.reply_text(
                    "Harga tidak valid. Masukkan angka saja, mis. 250000 atau 0."
                )
                return
            prod = await create_product(
                db,
                company_id=u.company_id,
                sku=fields["sku"],
                name=fields["name"],
                unit=fields.get("unit", "pcs"),
                sale_price=price,
            )
            await clear_state(db, chat_id)  # jaga-jaga bila ada alur menggantung
            await update.message.reply_text(
                f"Tersimpan: {prod.name} ({prod.sku}), satuan {prod.unit}, harga {price}.\n"
                "Cek di web Ananta -> menu Produk."
            )
            return

        # --- Mode terpandu: perintah dikirim polos ---
        await set_state(db, chat_id, "add_product", "sku", {})
    await update.message.reply_text(
        "Tambah produk baru.\nMasukkan SKU (mis. MNS-WHK):\n\n"
        "(ketik /batal kapan saja untuk membatalkan)\n\n"
        "Atau lain kali kirim sekaligus:\n" + PRODUCT_FORMAT_HINT
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    async with SessionLocal() as db:
        st = await load_state(db, chat_id)
        if st is None or not st.flow:
            return  # tidak ada alur aktif -> abaikan teks biasa
        draft = json.loads(st.draft or "{}")

        if st.flow == "add_product":
            # Jika user MENEMPEL blok format lengkap (ada SKU + Nama) di tengah
            # alur terpandu, kenali dan proses sekaligus -- jangan diperlakukan
            # sebagai satu jawaban langkah.
            blok = parse_product_block(text)
            if blok.get("sku") and blok.get("name"):
                u = await _linked_user(db, chat_id)
                if u is None:
                    await clear_state(db, chat_id)
                    await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                    return
                price = _parse_price(blok.get("price_raw", "0"))
                if price is None:
                    await update.message.reply_text(
                        "Harga tidak valid. Masukkan angka saja, mis. 250000 atau 0."
                    )
                    return
                prod = await create_product(
                    db,
                    company_id=u.company_id,
                    sku=blok["sku"],
                    name=blok["name"],
                    unit=blok.get("unit", "pcs"),
                    sale_price=price,
                )
                await clear_state(db, chat_id)
                await update.message.reply_text(
                    f"Tersimpan: {prod.name} ({prod.sku}), satuan {prod.unit}, harga {price}.\n"
                    "Cek di web Ananta -> menu Produk."
                )
                return

            if st.step == "sku":
                draft["sku"] = text[:40]
                await set_state(db, chat_id, "add_product", "name", draft)
                await update.message.reply_text("Nama produk:")
            elif st.step == "name":
                draft["name"] = text[:200]
                await set_state(db, chat_id, "add_product", "unit", draft)
                await update.message.reply_text(
                    "Satuan (mis. botol). Ketik tanda - untuk memakai 'pcs':"
                )
            elif st.step == "unit":
                draft["unit"] = "pcs" if text == "-" else text[:20]
                await set_state(db, chat_id, "add_product", "sale_price", draft)
                await update.message.reply_text(
                    "Harga jual (angka saja, mis. 250000). Ketik 0 bila belum ada:"
                )
            elif st.step == "sale_price":
                price = _parse_price(text)
                if price is None:
                    await update.message.reply_text(
                        "Harga tidak valid. Masukkan angka saja, mis. 250000:"
                    )
                    return
                draft["sale_price"] = str(price)
                await set_state(db, chat_id, "add_product", "confirm", draft)
                await update.message.reply_text(
                    "Konfirmasi produk baru:\n"
                    f"- SKU    : {draft['sku']}\n"
                    f"- Nama   : {draft['name']}\n"
                    f"- Satuan : {draft['unit']}\n"
                    f"- Harga  : {price}\n\n"
                    "Ketik YA untuk simpan, atau /batal."
                )
            elif st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text(
                            "Sesi tidak tertaut lagi. Ketik /link."
                        )
                        return
                    prod = await create_product(
                        db,
                        company_id=u.company_id,
                        sku=draft["sku"],
                        name=draft["name"],
                        unit=draft.get("unit", "pcs"),
                        sale_price=Decimal(draft.get("sale_price", "0")),
                    )
                    await clear_state(db, chat_id)
                    await update.message.reply_text(
                        f"Tersimpan: {prod.name} ({prod.sku}).\n"
                        "Cek di web Ananta -> menu Produk."
                    )
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")

        elif st.flow == "add_expense":
            if st.step == "amount":
                amount = parse_amount(text)
                if amount is None:
                    await update.message.reply_text(
                        "Jumlah tidak valid. Masukkan angka, mis. 150000:"
                    )
                    return
                draft["amount"] = str(amount)
                await set_state(db, chat_id, "add_expense", "description", draft)
                await update.message.reply_text("Untuk apa pengeluaran ini? (keterangan):")
            elif st.step == "description":
                draft["description"] = text[:255]
                await set_state(db, chat_id, "add_expense", "account", draft)
                await update.message.reply_text(
                    _menu("Pilih kategori beban (ketik nomor):", EXPENSE_ACCOUNTS)
                )
            elif st.step == "account":
                idx = _pick_index(text, len(EXPENSE_ACCOUNTS))
                if idx is None:
                    await update.message.reply_text("Ketik nomor yang valid dari daftar:")
                    return
                draft["exp_code"] = EXPENSE_ACCOUNTS[idx][0]
                await set_state(db, chat_id, "add_expense", "paid", draft)
                await update.message.reply_text(
                    _menu("Dibayar dari mana? (ketik nomor):", PAYMENT_ACCOUNTS)
                )
            elif st.step == "paid":
                idx = _pick_index(text, len(PAYMENT_ACCOUNTS))
                if idx is None:
                    await update.message.reply_text("Ketik nomor yang valid dari daftar:")
                    return
                draft["paid_code"] = PAYMENT_ACCOUNTS[idx][0]
                await set_state(db, chat_id, "add_expense", "confirm", draft)
                await update.message.reply_text(
                    "Konfirmasi pengeluaran:\n"
                    f"- Jumlah : Rp{draft['amount']}\n"
                    f"- Untuk  : {draft['description']}\n"
                    f"- Beban  : {draft['exp_code']}\n"
                    f"- Bayar  : {draft['paid_code']}\n\n"
                    "Ketik YA untuk simpan, atau /batal."
                )
            elif st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                        return
                    msg = await _do_create_expense(
                        db,
                        u,
                        Decimal(draft["amount"]),
                        draft["description"],
                        draft["exp_code"],
                        draft["paid_code"],
                    )
                    await clear_state(db, chat_id)
                    await update.message.reply_text(msg)
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")

        elif st.flow == "add_contact":
            if st.step == "type":
                idx = _pick_index(text, len(CONTACT_TYPES))
                if idx is None:
                    await update.message.reply_text("Ketik nomor yang valid dari daftar:")
                    return
                draft["type"] = CONTACT_TYPES[idx][0]
                await set_state(db, chat_id, "add_contact", "name", draft)
                await update.message.reply_text("Nama kontak:")
            elif st.step == "name":
                draft["name"] = text[:160]
                await set_state(db, chat_id, "add_contact", "phone", draft)
                await update.message.reply_text("Nomor HP (ketik - untuk kosong):")
            elif st.step == "phone":
                draft["phone"] = None if text == "-" else text[:40]
                await set_state(db, chat_id, "add_contact", "confirm", draft)
                await update.message.reply_text(
                    "Konfirmasi kontak:\n"
                    f"- Tipe : {draft['type']}\n"
                    f"- Nama : {draft['name']}\n"
                    f"- HP   : {draft.get('phone') or '-'}\n\n"
                    "Ketik YA untuk simpan, atau /batal."
                )
            elif st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                        return
                    contact = await create_contact(
                        db,
                        company_id=u.company_id,
                        type=draft["type"],
                        name=draft["name"],
                        phone=draft.get("phone"),
                    )
                    await clear_state(db, chat_id)
                    await update.message.reply_text(
                        f"Kontak tersimpan: {contact.name} ({contact.type}).\n"
                        "Cek di web Ananta -> menu Kontak."
                    )
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")

        elif st.flow == "add_loan":
            if st.step == "name":
                draft["name"] = text[:120]
                await set_state(db, chat_id, "add_loan", "amount", draft)
                await update.message.reply_text("Jumlah kasbon (angka, mis. 500000):")
            elif st.step == "amount":
                amount = parse_amount(text)
                if amount is None:
                    await update.message.reply_text(
                        "Jumlah tidak valid. Masukkan angka, mis. 500000:"
                    )
                    return
                draft["amount"] = str(amount)
                await set_state(db, chat_id, "add_loan", "paid", draft)
                await update.message.reply_text(
                    _menu("Dibayar dari mana? (ketik nomor):", PAYMENT_ACCOUNTS)
                )
            elif st.step == "paid":
                idx = _pick_index(text, len(PAYMENT_ACCOUNTS))
                if idx is None:
                    await update.message.reply_text("Ketik nomor yang valid dari daftar:")
                    return
                draft["paid_code"] = PAYMENT_ACCOUNTS[idx][0]
                await set_state(db, chat_id, "add_loan", "confirm", draft)
                await update.message.reply_text(
                    "Konfirmasi kasbon:\n"
                    f"- Nama   : {draft['name']}\n"
                    f"- Jumlah : Rp{draft['amount']}\n"
                    f"- Bayar  : {draft['paid_code']}\n\n"
                    "Ketik YA untuk simpan, atau /batal."
                )
            elif st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                        return
                    msg = await _do_create_loan(
                        db, u, draft["name"], Decimal(draft["amount"]), draft["paid_code"]
                    )
                    await clear_state(db, chat_id)
                    await update.message.reply_text(msg)
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")

        elif st.flow == "pay_supplier":
            if st.step == "ref":
                u0 = await _linked_user(db, chat_id)
                bill = await _find_bill(db, u0.company_id, text.strip()) if u0 else None
                if bill is None:
                    await update.message.reply_text(
                        "Faktur tidak ditemukan. Ketik ulang nomornya, atau /batal:"
                    )
                    return
                draft["bill_id"] = bill.id
                draft["bill_number"] = bill.number
                sisa = _sisa(bill)
                await set_state(db, chat_id, "pay_supplier", "amount", draft)
                extra = f"Sisa tagihan: Rp{sisa}\n" if sisa is not None else ""
                await update.message.reply_text(
                    f"Faktur {bill.number} ditemukan.\n{extra}Masukkan jumlah bayar:"
                )
            elif st.step == "amount":
                amount = parse_amount(text)
                if amount is None:
                    await update.message.reply_text("Jumlah tidak valid. Masukkan angka:")
                    return
                draft["amount"] = str(amount)
                await set_state(db, chat_id, "pay_supplier", "confirm", draft)
                await update.message.reply_text(
                    "Konfirmasi pembayaran supplier:\n"
                    f"- Faktur : {draft['bill_number']}\n"
                    f"- Jumlah : Rp{draft['amount']} (dari Kas)\n\n"
                    "Ketik YA untuk simpan, atau /batal."
                )
            elif st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                        return
                    msg = await _do_pay_supplier(
                        db, u, draft["bill_id"], draft["bill_number"], Decimal(draft["amount"])
                    )
                    await clear_state(db, chat_id)
                    await update.message.reply_text(msg)
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")

        elif st.flow == "pay_customer":
            if st.step == "ref":
                u0 = await _linked_user(db, chat_id)
                inv = await _find_invoice(db, u0.company_id, text.strip()) if u0 else None
                if inv is None:
                    await update.message.reply_text(
                        "Faktur tidak ditemukan. Ketik ulang nomornya, atau /batal:"
                    )
                    return
                draft["invoice_id"] = inv.id
                draft["invoice_number"] = inv.number
                sisa = _sisa(inv)
                await set_state(db, chat_id, "pay_customer", "amount", draft)
                extra = f"Sisa tagihan: Rp{sisa}\n" if sisa is not None else ""
                await update.message.reply_text(
                    f"Faktur {inv.number} ditemukan.\n{extra}Masukkan jumlah diterima:"
                )
            elif st.step == "amount":
                amount = parse_amount(text)
                if amount is None:
                    await update.message.reply_text("Jumlah tidak valid. Masukkan angka:")
                    return
                draft["amount"] = str(amount)
                await set_state(db, chat_id, "pay_customer", "confirm", draft)
                await update.message.reply_text(
                    "Konfirmasi penerimaan customer:\n"
                    f"- Faktur : {draft['invoice_number']}\n"
                    f"- Jumlah : Rp{draft['amount']} (ke Kas)\n\n"
                    "Ketik YA untuk simpan, atau /batal."
                )
            elif st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                        return
                    msg = await _do_pay_customer(
                        db, u, draft["invoice_id"], draft["invoice_number"], Decimal(draft["amount"])
                    )
                    await clear_state(db, chat_id)
                    await update.message.reply_text(msg)
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")

        elif st.flow == "pengadaan":
            if st.step == "confirm":
                if text.lower() in ("ya", "y", "iya"):
                    u = await _linked_user(db, chat_id)
                    if u is None:
                        await clear_state(db, chat_id)
                        await update.message.reply_text("Sesi tidak tertaut lagi. Ketik /link.")
                        return
                    on_date = (datetime.now(timezone.utc) + timedelta(hours=7)).date()
                    lines_in = [
                        {
                            "product_id": ln["product_id"],
                            "quantity": Decimal(ln["quantity"]),
                            "unit_cost": Decimal(ln["unit_cost"]),
                        }
                        for ln in draft["lines"]
                    ]
                    try:
                        bill = await create_and_post_bill(
                            db,
                            company_id=u.company_id,
                            user_id=u.id,
                            contact_id=draft["contact_id"],
                            on_date=on_date,
                            warehouse_id=draft.get("warehouse_id"),
                            lines_in=lines_in,
                            notes=None,
                        )
                        await db.commit()
                    except (JournalNotBalanced, ValueError) as e:
                        await db.rollback()
                        await clear_state(db, chat_id)
                        await update.message.reply_text(f"Gagal: {e}")
                        return
                    except Exception:
                        await db.rollback()
                        await clear_state(db, chat_id)
                        await update.message.reply_text(
                            "Gagal menyimpan pengadaan (kesalahan tak terduga)."
                        )
                        return
                    await db.refresh(bill)
                    await clear_state(db, chat_id)
                    await update.message.reply_text(
                        f"Pengadaan tersimpan: {bill.number}\n"
                        f"Supplier: {draft['supplier_name']}\n"
                        "Cek di web Ananta -> menu Pembelian."
                    )
                else:
                    await update.message.reply_text("Ketik YA untuk simpan, atau /batal.")


async def _do_create_expense(db, u, amount, description, exp_code, paid_code):
    on_date = (datetime.now(timezone.utc) + timedelta(hours=7)).date()  # tanggal WIB
    try:
        exp = await create_expense(
            db,
            company_id=u.company_id,
            user_id=u.id,
            on_date=on_date,
            category="umum",
            description=description,
            amount=amount,
            expense_account_code=exp_code,
            paid_account_code=paid_code,
            note=None,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        return f"Gagal: {e}"
    except Exception:
        await db.rollback()
        return "Gagal menyimpan pengeluaran (kesalahan tak terduga)."
    await db.refresh(exp)
    return (
        f"Pengeluaran tersimpan: {exp.number}\n"
        f"{description} - Rp{amount}\n"
        f"Beban {exp_code}, dibayar dari {paid_code}.\n"
        "Cek di web Ananta -> menu Biaya."
    )


async def cmd_tambah_pengeluaran(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(EXPENSE_ROLES):
            await update.message.reply_text("Kamu tidak punya akses menambah pengeluaran.")
            return

        # --- Mode sekali-kirim ---
        if body:
            f = parse_expense_block(body)
            amount = parse_amount(f.get("amount_raw", ""))
            if amount is None:
                await update.message.reply_text(
                    "Jumlah tidak valid.\n\n" + EXPENSE_FORMAT_HINT
                )
                return
            desc = f.get("description")
            if not desc:
                await update.message.reply_text(
                    "Keterangan (baris 'Untuk:') wajib diisi.\n\n" + EXPENSE_FORMAT_HINT
                )
                return
            exp_code = resolve_expense_account(f.get("expense_raw", "")) or DEFAULT_EXPENSE_CODE
            paid_code = resolve_payment_account(f.get("paid_raw", "")) or DEFAULT_PAID_CODE
            msg = await _do_create_expense(db, u, amount, desc, exp_code, paid_code)
            await clear_state(db, chat_id)
            await update.message.reply_text(msg)
            return

        # --- Mode terpandu ---
        await set_state(db, chat_id, "add_expense", "amount", {})
    await update.message.reply_text(
        "Tambah pengeluaran.\nMasukkan JUMLAH (angka, mis. 150000):\n\n"
        "(ketik /batal kapan saja untuk membatalkan)\n\n"
        "Atau lain kali kirim sekaligus:\n" + EXPENSE_FORMAT_HINT
    )


async def cmd_tambah_kontak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(CONTACT_ROLES):
            await update.message.reply_text("Kamu tidak punya akses menambah kontak.")
            return

        # --- Mode sekali-kirim ---
        if body:
            f = parse_contact_block(body)
            name = f.get("name")
            ctype = resolve_contact_type(f.get("type_raw", ""))
            if not name:
                await update.message.reply_text(
                    "Nama wajib diisi.\n\n" + CONTACT_FORMAT_HINT
                )
                return
            if ctype is None:
                await update.message.reply_text(
                    "Tipe wajib: customer / supplier / keduanya.\n\n" + CONTACT_FORMAT_HINT
                )
                return
            contact = await create_contact(
                db, company_id=u.company_id, type=ctype, name=name, phone=f.get("phone")
            )
            await clear_state(db, chat_id)
            await update.message.reply_text(
                f"Kontak tersimpan: {contact.name} ({contact.type}).\n"
                "Cek di web Ananta -> menu Kontak."
            )
            return

        # --- Mode terpandu ---
        await set_state(db, chat_id, "add_contact", "type", {})
    await update.message.reply_text(
        _menu("Tambah kontak. Pilih tipe (ketik nomor):", CONTACT_TYPES)
        + "\n\n(ketik /batal untuk membatalkan)\n\nAtau lain kali kirim sekaligus:\n"
        + CONTACT_FORMAT_HINT
    )


async def _do_create_loan(db, u, employee_name, amount, paid_code):
    on_date = (datetime.now(timezone.utc) + timedelta(hours=7)).date()  # WIB
    try:
        loan = await create_loan(
            db,
            company_id=u.company_id,
            user_id=u.id,
            employee_name=employee_name,
            on_date=on_date,
            amount=amount,
            paid_account_code=paid_code,
            note=None,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        return f"Gagal: {e}"
    except Exception:
        await db.rollback()
        return "Gagal menyimpan kasbon (kesalahan tak terduga)."
    await db.refresh(loan)
    return (
        f"Kasbon tersimpan: {loan.number}\n"
        f"{employee_name} - Rp{amount}\n"
        f"Dibayar dari {paid_code}.\n"
        "Cek di web Ananta -> menu Kasbon."
    )


async def cmd_kasbon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(KASBON_ROLES):
            await update.message.reply_text("Kamu tidak punya akses mencatat kasbon.")
            return

        # --- Mode sekali-kirim ---
        if body:
            f = parse_loan_block(body)
            name = f.get("name")
            amount = parse_amount(f.get("amount_raw", ""))
            if not name:
                await update.message.reply_text(
                    "Nama karyawan wajib diisi.\n\n" + KASBON_FORMAT_HINT
                )
                return
            if amount is None:
                await update.message.reply_text(
                    "Jumlah tidak valid.\n\n" + KASBON_FORMAT_HINT
                )
                return
            paid_code = resolve_payment_account(f.get("paid_raw", "")) or DEFAULT_PAID_CODE
            msg = await _do_create_loan(db, u, name, amount, paid_code)
            await clear_state(db, chat_id)
            await update.message.reply_text(msg)
            return

        # --- Mode terpandu ---
        await set_state(db, chat_id, "add_loan", "name", {})
    await update.message.reply_text(
        "Catat kasbon.\nNama karyawan:\n\n"
        "(ketik /batal untuk membatalkan)\n\nAtau lain kali kirim sekaligus:\n"
        + KASBON_FORMAT_HINT
    )


async def _find_bill(db, company_id, number):
    return (
        await db.execute(
            select(Bill).where(Bill.company_id == company_id, Bill.number == number)
        )
    ).scalar_one_or_none()


async def _find_invoice(db, company_id, number):
    return (
        await db.execute(
            select(Invoice).where(
                Invoice.company_id == company_id, Invoice.number == number
            )
        )
    ).scalar_one_or_none()


def _sisa(doc):
    try:
        return doc.total - doc.paid_total
    except Exception:
        return None


async def _do_pay_supplier(db, u, bill_id, bill_number, amount):
    on_date = (datetime.now(timezone.utc) + timedelta(hours=7)).date()
    try:
        pm = await pay_bill(
            db, company_id=u.company_id, user_id=u.id,
            bill_id=bill_id, on_date=on_date, amount=amount, cash_account_id=None,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        return f"Gagal: {e}"
    except Exception:
        await db.rollback()
        return "Gagal menyimpan pembayaran (kesalahan tak terduga)."
    await db.refresh(pm)
    return (
        f"Pembayaran supplier tersimpan: {pm.number}\n"
        f"Faktur {bill_number} - Rp{amount} (dari Kas).\n"
        "Cek di web Ananta -> menu Pembayaran."
    )


async def _do_pay_customer(db, u, invoice_id, invoice_number, amount):
    on_date = (datetime.now(timezone.utc) + timedelta(hours=7)).date()
    try:
        pr = await receive_payment(
            db, company_id=u.company_id, user_id=u.id,
            invoice_id=invoice_id, on_date=on_date, amount=amount, cash_account_id=None,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        return f"Gagal: {e}"
    except Exception:
        await db.rollback()
        return "Gagal menyimpan penerimaan (kesalahan tak terduga)."
    await db.refresh(pr)
    return (
        f"Penerimaan customer tersimpan: {pr.number}\n"
        f"Faktur {invoice_number} - Rp{amount} (ke Kas).\n"
        "Cek di web Ananta -> menu Pembayaran."
    )


async def cmd_bayar_supplier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(PAYMENT_ROLES):
            await update.message.reply_text("Kamu tidak punya akses mencatat pembayaran.")
            return

        if body:
            f = parse_payment_block(body)
            ref = f.get("ref")
            amount = parse_amount(f.get("amount_raw", ""))
            if not ref or amount is None:
                await update.message.reply_text(
                    "Faktur & Jumlah wajib.\n\n" + PAY_SUPPLIER_HINT
                )
                return
            bill = await _find_bill(db, u.company_id, ref)
            if bill is None:
                await update.message.reply_text(f"Faktur pembelian {ref} tidak ditemukan.")
                return
            msg = await _do_pay_supplier(db, u, bill.id, bill.number, amount)
            await clear_state(db, chat_id)
            await update.message.reply_text(msg)
            return

        await set_state(db, chat_id, "pay_supplier", "ref", {})
    await update.message.reply_text(
        "Bayar supplier.\nMasukkan NOMOR faktur pembelian (mis. BILL/2026/0001):\n\n"
        "(ketik /batal untuk membatalkan)\n\nAtau kirim sekaligus:\n" + PAY_SUPPLIER_HINT
    )


async def cmd_bayar_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(PAYMENT_ROLES):
            await update.message.reply_text("Kamu tidak punya akses mencatat penerimaan.")
            return

        if body:
            f = parse_payment_block(body)
            ref = f.get("ref")
            amount = parse_amount(f.get("amount_raw", ""))
            if not ref or amount is None:
                await update.message.reply_text(
                    "Faktur & Jumlah wajib.\n\n" + PAY_CUSTOMER_HINT
                )
                return
            inv = await _find_invoice(db, u.company_id, ref)
            if inv is None:
                await update.message.reply_text(f"Faktur penjualan {ref} tidak ditemukan.")
                return
            msg = await _do_pay_customer(db, u, inv.id, inv.number, amount)
            await clear_state(db, chat_id)
            await update.message.reply_text(msg)
            return

        await set_state(db, chat_id, "pay_customer", "ref", {})
    await update.message.reply_text(
        "Terima pembayaran customer.\nMasukkan NOMOR faktur penjualan (mis. INV/2026/0001):\n\n"
        "(ketik /batal untuk membatalkan)\n\nAtau kirim sekaligus:\n" + PAY_CUSTOMER_HINT
    )


async def _find_supplier(db, company_id, name):
    q = name.strip().lower()
    rows = (
        await db.execute(
            select(Contact).where(
                Contact.company_id == company_id,
                Contact.type.in_(["supplier", "both"]),
            )
        )
    ).scalars().all()
    exact = [c for c in rows if (c.name or "").lower() == q]
    if len(exact) == 1:
        return exact[0], None
    contains = [c for c in rows if q in (c.name or "").lower()]
    if len(contains) == 1:
        return contains[0], None
    if not contains:
        return None, f"Supplier '{name}' tidak ditemukan. Tambah via /tambah_kontak."
    names = ", ".join(c.name for c in contains[:5])
    return None, f"Beberapa supplier cocok: {names}. Sebutkan lebih tepat."


async def _find_product_by_sku(db, company_id, sku):
    return (
        await db.execute(
            select(Product).where(
                Product.company_id == company_id,
                func.upper(Product.sku) == sku.upper(),
            )
        )
    ).scalar_one_or_none()


async def _resolve_warehouse_id(db, company_id, name):
    rows = (
        await db.execute(select(Warehouse).where(Warehouse.company_id == company_id))
    ).scalars().all()
    if name:
        q = name.strip().lower()
        m = [w for w in rows if q in (w.name or "").lower()]
        if len(m) == 1:
            return m[0].id
        return None  # ambigu/none -> tak ditetapkan
    if len(rows) == 1:
        return rows[0].id
    return None


async def cmd_pengadaan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    full_text = update.message.text or ""
    parts = full_text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""

    async with SessionLocal() as db:
        u = await _linked_user(db, chat_id)
        if u is None:
            await update.message.reply_text("Akun belum tertaut. Ketik /link dulu.")
            return
        roles = await user_roles(db, u.id)
        if "owner" not in roles and not roles.intersection(PENGADAAN_ROLES):
            await update.message.reply_text("Kamu tidak punya akses membuat pengadaan.")
            return

        if not body:
            await update.message.reply_text("Buat faktur pembelian.\n\n" + PENGADAAN_HINT)
            return

        parsed = parse_pengadaan_block(body)
        if not parsed["supplier"] or not parsed["items"]:
            await update.message.reply_text(
                "Supplier dan minimal satu Item wajib.\n\n" + PENGADAAN_HINT
            )
            return

        supplier, err = await _find_supplier(db, u.company_id, parsed["supplier"])
        if err:
            await update.message.reply_text(err)
            return

        wh_id = await _resolve_warehouse_id(db, u.company_id, parsed["warehouse"])

        lines = []
        errors = []
        total = Decimal("0")
        summary_lines = []
        for i, raw in enumerate(parsed["items"], 1):
            item = parse_item_line(raw)
            if item is None:
                errors.append(f"Baris {i} salah format: '{raw}'")
                continue
            sku, qty, price = item
            prod = await _find_product_by_sku(db, u.company_id, sku)
            if prod is None:
                errors.append(f"SKU '{sku}' tidak ditemukan (baris {i})")
                continue
            subtotal = qty * price
            total += subtotal
            lines.append(
                {"product_id": prod.id, "quantity": str(qty), "unit_cost": str(price)}
            )
            summary_lines.append(f"- {prod.name} ({sku}) x {qty} @ {price} = {subtotal}")

        if errors:
            await update.message.reply_text(
                "Tidak jadi disimpan. Perbaiki dulu:\n" + "\n".join(errors)
            )
            return

        draft = {
            "contact_id": supplier.id,
            "supplier_name": supplier.name,
            "warehouse_id": wh_id,
            "lines": lines,
        }
        await set_state(db, chat_id, "pengadaan", "confirm", draft)
    await update.message.reply_text(
        "Konfirmasi pengadaan:\n"
        f"Supplier: {supplier.name}\n"
        + "\n".join(summary_lines)
        + f"\n\nTotal: Rp{total}\n\nKetik YA untuk simpan, atau /batal."
    )


def register(application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("bantuan", cmd_help))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("link", cmd_link))
    application.add_handler(CommandHandler("buat_kode", cmd_buat_kode))
    application.add_handler(CommandHandler("batal", cmd_batal))
    application.add_handler(CommandHandler("tambah_produk", cmd_tambah_produk))
    application.add_handler(CommandHandler("tambah_pengeluaran", cmd_tambah_pengeluaran))
    application.add_handler(CommandHandler("tambah_kontak", cmd_tambah_kontak))
    application.add_handler(CommandHandler("kasbon", cmd_kasbon))
    application.add_handler(CommandHandler("bayar_supplier", cmd_bayar_supplier))
    application.add_handler(CommandHandler("bayar_customer", cmd_bayar_customer))
    application.add_handler(CommandHandler("pengadaan", cmd_pengadaan))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
