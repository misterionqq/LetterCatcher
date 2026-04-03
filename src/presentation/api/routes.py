from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.use_cases.manage_users import ManageUsersUseCase
from src.presentation.api.security import create_access_token, get_current_user_id
from src.presentation.api.dependencies import get_user_use_case
from src.presentation.api.schemas import (
    TokenRequest, TokenResponse,
    UserOut, KeywordOut, SetEmailRequest, SetSensitivityRequest,
    AddKeywordRequest, AddStopWordRequest,
    EmailHistoryItem, StatsOut,
    DndToggleOut, PendingNotificationOut,
    HealthOut,
)

router = APIRouter()


# ============= Health =============

@router.get("/health", response_model=HealthOut, tags=["system"])
async def health():
    return HealthOut()


# ============= Auth =============

@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
async def get_token(
    body: TokenRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    user = await uc.get_user_profile(body.telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not registered. Use the Telegram bot first.")
    token = create_access_token(body.telegram_id)
    return TokenResponse(access_token=token)


# ============= Profile =============

@router.get("/profile", response_model=UserOut, tags=["profile"])
async def get_profile(
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    user = await uc.get_user_profile(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        telegram_id=user.telegram_id,
        email=user.email,
        ai_sensitivity=user.ai_sensitivity,
        is_dnd=user.is_dnd,
        keywords=[KeywordOut(word=kw.word, is_stop_word=kw.is_stop_word) for kw in user.keywords],
    )


@router.put("/profile/email", response_model=UserOut, tags=["profile"])
async def set_email(
    body: SetEmailRequest,
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        await uc.set_email(tg_id, body.email)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid email format")
    return await get_profile(tg_id=tg_id, uc=uc)


@router.put("/profile/sensitivity", response_model=UserOut, tags=["profile"])
async def set_sensitivity(
    body: SetSensitivityRequest,
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    await uc.set_sensitivity(tg_id, body.level)
    return await get_profile(tg_id=tg_id, uc=uc)


# ============= DND =============

@router.post("/profile/dnd", response_model=DndToggleOut, tags=["profile"])
async def toggle_dnd(
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    new_state, pending = await uc.toggle_dnd(tg_id)
    return DndToggleOut(is_dnd=new_state, pending_count=len(pending))


@router.get("/profile/dnd/pending", response_model=List[PendingNotificationOut], tags=["profile"])
async def get_pending_notifications(
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    pending = await uc.user_repo.get_pending_notifications(tg_id)
    return [
        PendingNotificationOut(
            id=n.id, email_uid=n.email_uid, sender=n.sender,
            subject=n.subject, body_snippet=n.body_snippet,
            ai_reason=n.ai_reason, triggered_word=n.triggered_word,
            action_url=n.action_url, created_at=n.created_at,
        )
        for n in pending
    ]


# ============= Keywords =============

@router.post("/keywords", response_model=UserOut, tags=["keywords"])
async def add_keyword(
    body: AddKeywordRequest,
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        await uc.add_trigger_word(tg_id, body.word)
    except ValueError:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    return await get_profile(tg_id=tg_id, uc=uc)


@router.post("/keywords/stop", response_model=UserOut, tags=["keywords"])
async def add_stop_word(
    body: AddStopWordRequest,
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        await uc.add_stop_word(tg_id, body.word)
    except ValueError:
        raise HTTPException(status_code=409, detail="Stop word already exists")
    return await get_profile(tg_id=tg_id, uc=uc)


@router.delete("/keywords/{word}", response_model=UserOut, tags=["keywords"])
async def remove_keyword(
    word: str,
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    await uc.user_repo.remove_keyword(tg_id, word)
    return await get_profile(tg_id=tg_id, uc=uc)


# ============= Email history & stats =============

@router.get("/emails/history", response_model=List[EmailHistoryItem], tags=["emails"])
async def get_email_history(
    limit: int = 10,
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    history = await uc.get_email_history(tg_id, limit=limit)
    return [EmailHistoryItem(**item) for item in history]


@router.get("/emails/stats", response_model=StatsOut, tags=["emails"])
async def get_stats(
    tg_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    stats = await uc.get_stats(tg_id)
    return StatsOut(**stats)
