"""Legal search and chat API."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import ChatMessage, ChatSession, User
from app.schemas.schemas import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.llm_service import chat_reply, legal_search

router = APIRouter(tags=["legal"])


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, _user: User = Depends(get_current_user)):
    answer, refs = await legal_search(body.query, body.search_type)
    return SearchResponse(answer=answer, search_type=body.search_type, references=refs)


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session: ChatSession | None = None
    if body.session_id:
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == body.session_id, ChatSession.user_id == user.id)
        )
        session = result.scalar_one_or_none()
    if session is None:
        session = ChatSession(
            user_id=user.id,
            module=body.module,
            title=body.message[:30] or "新对话",
        )
        db.add(session)
        await db.flush()

    user_msg = ChatMessage(session_id=session.id, role="user", content=body.message)
    db.add(user_msg)
    await db.flush()

    reply_text = await chat_reply(body.message, body.module)
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=reply_text)
    db.add(assistant_msg)
    session.title = session.title or body.message[:30]
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return ChatResponse(
        session_id=session.id,
        message=ChatMessageResponse.model_validate(user_msg),
        reply=ChatMessageResponse.model_validate(assistant_msg),
    )


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    module: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.updated_at.desc())
    if module:
        q = q.where(ChatSession.module == module)
    result = await db.execute(q.limit(50))
    return result.scalars().all()


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def session_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return []
    msgs = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
    )
    return msgs.scalars().all()
