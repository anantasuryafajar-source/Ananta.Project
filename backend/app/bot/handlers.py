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
from ..models import Role, TelegramLink, User, UserRole
from ..services.product_service import create_product
from ..services.expense_service import create_expense
from ..services.journal import JournalNotBalanced
from .parsing import (
    DEFAULT_EXPENSE_CODE,
    DEFAULT_PAID_CODE,
    EXPENSE_ACCOUNTS,
    PAYMENT_ACCOUNTS,
    parse_amount,
    parse_expense_block,
    resolve_expense_account,
    resolve_payment_account,
)
from .state import clear_state, load_state, set_state

# Peran yang boleh menambah produk (owner selalu lolos).
PRODUCT_ROLES = {"warehouse", "finance", "sales"}
EXPENSE_ROLES = {"finance"}

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


def register(application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("bantuan", cmd_help))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("link", cmd_link))
    application.add_handler(CommandHandler("buat_kode", cmd_buat_kode))
    application.add_handler(CommandHandler("batal", cmd_batal))
    application.add_handler(CommandHandler("tambah_produk", cmd_tambah_produk))
    application.add_handler(CommandHandler("tambah_pengeluaran", cmd_tambah_pengeluaran))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
