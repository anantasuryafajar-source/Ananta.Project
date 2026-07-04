"""State percakapan terpandu, disimpan di DB (aman untuk banyak worker)."""
import json
from sqlalchemy import select
from ..models import TelegramSession


async def load_state(db, chat_id: int) -> TelegramSession | None:
    return (
        await db.execute(
            select(TelegramSession).where(TelegramSession.telegram_chat_id == chat_id)
        )
    ).scalar_one_or_none()


async def set_state(db, chat_id: int, flow: str, step: str, draft: dict) -> None:
    s = await load_state(db, chat_id)
    if s is None:
        s = TelegramSession(telegram_chat_id=chat_id)
        db.add(s)
    s.flow = flow
    s.step = step
    s.draft = json.dumps(draft)
    await db.commit()


async def clear_state(db, chat_id: int) -> None:
    s = await load_state(db, chat_id)
    if s is not None:
        s.flow = None
        s.step = None
        s.draft = None
        await db.commit()
