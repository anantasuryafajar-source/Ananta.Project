"""Endpoint Asisten AI web. Mount di /api/v1/ai/...

Slash command PROFILING 2.0:
    /profiling Nama Lengkap
    /profling Nama Lengkap                  # alias salah ketik
    /profiling Nama | Jabatan | Instansi | Wilayah | Periode

Hasil profiling masuk ke percakapan yang sama dan tersimpan sebagai AiMessage.
Tidak diperlukan halaman atau menu sidebar terpisah.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..deps import require_roles
from ..models import AiConversation, AiMessage, User
from ..services import ai
from ..services import profiling
from ..services.profiling_command import (
    parse_profiling_command,
    profiling_reply,
    profiling_usage,
)

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatIn(BaseModel):
    conversation_id: str | None = None
    message: str
    mode: str | None = None
    model: str | None = None
    effort: str | None = None
    attachments: list[dict] | None = None



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
        "modes": [{"id": m, "label": ai.MODE_LABELS[m]} for m in ai.MODES],
        "default_mode": ai.DEFAULT_MODE,
        "efforts": [
            {"id": "low", "label": "Rendah"},
            {"id": "medium", "label": "Sedang"},
            {"id": "high", "label": "Tinggi"},
        ],
        "default_effort": ai.DEFAULT_EFFORT,
        "commands": [
            {
                "id": "profiling",
                "syntax": "/profiling Nama Lengkap",
                "description": "Jalankan PROFILING 2.0 untuk figur publik.",
                "aliases": ["/profling"],
            }
        ],
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

    is_profile_command, profile_target = parse_profiling_command(text)

    # Lampiran hanya diteruskan ke jalur asisten biasa. PROFILING 2.0 melakukan
    # riset publik berdasarkan nama/konteks dalam slash command.
    att_blocks = []
    note = ""
    if body.attachments and not is_profile_command:
        max_size = 10 * 1024 * 1024
        total = sum(len(a.get("data") or "") for a in body.attachments)
        if total > max_size:
            raise HTTPException(status_code=413, detail="Lampiran terlalu besar (maks ~7MB).")
        for attachment in body.attachments[:5]:
            kind = attachment.get("kind")
            data = attachment.get("data")
            media = attachment.get("media_type")
            if not data or not media:
                continue
            if kind == "image":
                att_blocks.append(
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}
                )
            else:
                att_blocks.append(
                    {"type": "document", "source": {"type": "base64", "media_type": media, "data": data}}
                )
        if att_blocks:
            note = f" [dengan {len(att_blocks)} lampiran]"

    # Ambil / buat percakapan.
    if body.conversation_id:
        conv = await _owned_conv(db, body.conversation_id, user)
    else:
        if is_profile_command and profile_target:
            title = f"Profiling — {profile_target['name']}"[:60]
        elif is_profile_command:
            title = "PROFILING 2.0"
        else:
            title = text[:60]
        conv = AiConversation(
            company_id=user.company_id,
            user_id=user.id,
            title=title,
        )
        db.add(conv)
        await db.flush()

    db.add(AiMessage(conversation_id=conv.id, role="user", content=text + note))
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Jalur khusus slash command. Tidak masuk ke prompt umum yang melarang
    # profiling personal, karena modul ini memiliki guardrail publik tersendiri.
    if is_profile_command:
        if profile_target is None:
            reply = profiling_usage()
            final_model = getattr(profiling, "DEFAULT_PROFILING_MODEL", "gpt-5.6-terra")
        else:
            try:
                result = await profiling.generate_profile(
                    profile_target,
                    model=body.model,
                    effort=body.effort,
                    include_images=True,
                )
                reply = profiling_reply(result)
                final_model = result.get("model") or profiling.DEFAULT_PROFILING_MODEL
            except profiling.ProfilingError as exc:
                reply = f"PROFILING 2.0 belum dapat dijalankan: {exc}"
                final_model = profiling.DEFAULT_PROFILING_MODEL

        db.add(AiMessage(conversation_id=conv.id, role="assistant", content=reply))
        conv.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {
            "conversation_id": conv.id,
            "title": conv.title,
            "reply": reply,
            "mode": "profile",
            "mode_detected": False,
            "model": final_model,
            "command": "profiling",
        }

    rows = (
        await db.execute(
            select(AiMessage)
            .where(AiMessage.conversation_id == conv.id)
            .order_by(AiMessage.created_at.asc())
        )
    ).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in rows]

    result = await ai.answer(
        history,
        company_id=user.company_id,
        mode=body.mode,
        model=body.model,
        effort=body.effort,
        attachments=att_blocks or None,
    )

    db.add(AiMessage(conversation_id=conv.id, role="assistant", content=result.reply))
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "reply": result.reply,
        "mode": result.mode,
        "mode_detected": result.mode_detected,
        "model": result.model,
    }
