"""Endpoint Asisten AI web. Mount di /api/v1/ai/... (TERPISAH dari bot Telegram).

- POST   /ai/chat                       kirim pesan, dapat balasan (+persist)
- GET    /ai/conversations              daftar percakapan pengguna
- GET    /ai/conversations/{id}/messages   isi satu percakapan
- DELETE /ai/conversations/{id}         hapus percakapan
- GET    /ai/config                     daftar model & effort untuk dropdown
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..deps import require_roles
from ..models import AiConversation, AiMessage, User
from ..services import ai_assistant as ai

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatIn(BaseModel):
    conversation_id: str | None = None
    message: str
    model: str | None = None
    effort: str | None = None
    attachments: list[dict] | None = None  # [{kind:"document"|"image", media_type, data(base64)}]


async def _owned_conv(db: AsyncSession, conv_id: str, user: User) -> AiConversation:
    conv = (
        await db.execute(
            select(AiConversation).where(
                AiConversation.id == conv_id,
                AiConversation.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan.")
    return conv


@router.get("/config")
async def ai_config(user: User = Depends(require_roles("finance"))):
    return {
        "models": [{"id": k, "label": v} for k, v in ai.ALL_MODELS.items()],
        "default_model": ai.DEFAULT_MODEL,
        "efforts": [
            {"id": "low", "label": "Rendah"},
            {"id": "medium", "label": "Sedang"},
            {"id": "high", "label": "Tinggi"},
        ],
        "default_effort": ai.DEFAULT_EFFORT,
    }


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("finance")),
):
    rows = (
        await db.execute(
            select(AiConversation)
            .where(AiConversation.user_id == user.id)
            .order_by(AiConversation.updated_at.desc())
        )
    ).scalars().all()
    return [
        {"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows
    ]


@router.get("/conversations/{conv_id}/messages")
async def conversation_messages(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("finance")),
):
    await _owned_conv(db, conv_id, user)
    rows = (
        await db.execute(
            select(AiMessage)
            .where(AiMessage.conversation_id == conv_id)
            .order_by(AiMessage.created_at.asc())
        )
    ).scalars().all()
    return [{"role": m.role, "content": m.content} for m in rows]


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("finance")),
):
    await _owned_conv(db, conv_id, user)
    await db.execute(delete(AiMessage).where(AiMessage.conversation_id == conv_id))
    await db.execute(delete(AiConversation).where(AiConversation.id == conv_id))
    await db.commit()
    return {"ok": True}


@router.post("/chat")
async def chat(
    body: ChatIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("finance")),
):
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pesan kosong.")

    # Bangun blok lampiran (PDF/gambar) untuk dikirim ke AI. Batas ~10MB base64.
    att_blocks = []
    note = ""
    if body.attachments:
        MAX = 10 * 1024 * 1024
        total = sum(len(a.get("data") or "") for a in body.attachments)
        if total > MAX:
            raise HTTPException(status_code=413, detail="Lampiran terlalu besar (maks ~7MB).")
        for a in body.attachments[:5]:
            kind = a.get("kind")
            data = a.get("data")
            media = a.get("media_type")
            if not data or not media:
                continue
            if kind == "image":
                att_blocks.append(
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}
                )
            else:  # document (PDF dll)
                att_blocks.append(
                    {"type": "document", "source": {"type": "base64", "media_type": media, "data": data}}
                )
        if att_blocks:
            note = f" [dengan {len(att_blocks)} lampiran]"

    # Ambil / buat percakapan
    if body.conversation_id:
        conv = await _owned_conv(db, body.conversation_id, user)
    else:
        conv = AiConversation(
            company_id=user.company_id,
            user_id=user.id,
            title=text[:60],
        )
        db.add(conv)
        await db.flush()

    # Simpan pesan pengguna (dengan penanda lampiran bila ada)
    db.add(AiMessage(conversation_id=conv.id, role="user", content=text + note))
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Susun riwayat untuk AI
    rows = (
        await db.execute(
            select(AiMessage)
            .where(AiMessage.conversation_id == conv.id)
            .order_by(AiMessage.created_at.asc())
        )
    ).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in rows]

    reply = await ai.answer(
        history, company_id=user.company_id, model=body.model, effort=body.effort,
        attachments=att_blocks or None,
    )

    # Simpan balasan
    db.add(AiMessage(conversation_id=conv.id, role="assistant", content=reply))
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"conversation_id": conv.id, "title": conv.title, "reply": reply}
