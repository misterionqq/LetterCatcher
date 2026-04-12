from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError, jwt
from sqlalchemy import text

from src.use_cases.manage_users import ManageUsersUseCase
from src.infrastructure.config import JWT_SECRET_KEY, JWT_ALGORITHM
from src.infrastructure.database.setup import AsyncSessionLocal
from src.presentation.api.security import create_access_token, get_current_user_id
from src.presentation.api.dependencies import get_user_use_case, get_scanner
from src.presentation.api.ws_manager import ws_manager
from src.presentation.api.schemas import (
    TokenRequest, WebRegisterRequest, WebLoginRequest, TokenResponse,
    UserOut, KeywordOut, SetEmailRequest, SetSensitivityRequest,
    AddKeywordRequest, AddStopWordRequest,
    DeviceTokenRequest,
    EmailHistoryItem, StatsOut,
    DndToggleOut, PendingNotificationOut,
    HealthOut,
)

router = APIRouter()


# ============= Health =============

@router.get("/health", response_model=HealthOut, tags=["system"])
async def health():
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    scanner = get_scanner()
    scanner_status = "running" if scanner and scanner.is_running else "stopped"

    overall = "ok" if db_status == "ok" else "degraded"
    return HealthOut(status=overall, database=db_status, scanner=scanner_status)


# ============= Auth =============

@router.post("/auth/web/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, tags=["auth"])
async def web_register(
    body: WebRegisterRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Register a new user via email + password (web / mobile app)."""
    try:
        user = await uc.register_web_user(body.email, body.password)
    except ValueError as e:
        detail = str(e)
        if detail == "email_taken":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/web/login", response_model=TokenResponse, tags=["auth"])
async def web_login(
    body: WebLoginRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Login with email + password (web / mobile app)."""
    user = await uc.authenticate_web_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
async def get_token(
    body: TokenRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Login via Telegram ID (for users registered through the Telegram bot)."""
    user = await uc.get_user_profile_by_tg_id(body.telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not registered. Use the Telegram bot first.")
    return TokenResponse(access_token=create_access_token(user.id))


# ============= Profile =============

def _user_out(user) -> UserOut:
    return UserOut(
        telegram_id=user.telegram_id,
        email=user.email,
        ai_sensitivity=user.ai_sensitivity,
        is_dnd=user.is_dnd,
        keywords=[KeywordOut(word=kw.word, is_stop_word=kw.is_stop_word) for kw in user.keywords],
    )


@router.get("/profile", response_model=UserOut, tags=["profile"])
async def get_profile(
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    user = await uc.get_user_profile(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(user)


@router.put("/profile/email", response_model=UserOut, tags=["profile"])
async def set_email(
    body: SetEmailRequest,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        await uc.set_email(user_id, body.email)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid email format")
    return await get_profile(user_id=user_id, uc=uc)


@router.put("/profile/sensitivity", response_model=UserOut, tags=["profile"])
async def set_sensitivity(
    body: SetSensitivityRequest,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    await uc.set_sensitivity(user_id, body.level)
    return await get_profile(user_id=user_id, uc=uc)


# ============= DND =============

@router.post("/profile/dnd", response_model=DndToggleOut, tags=["profile"])
async def toggle_dnd(
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    new_state, pending = await uc.toggle_dnd(user_id)
    return DndToggleOut(is_dnd=new_state, pending_count=len(pending))


@router.get("/profile/dnd/pending", response_model=List[PendingNotificationOut], tags=["profile"])
async def get_pending_notifications(
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    pending = await uc.user_repo.get_pending_notifications(user_id)
    return [
        PendingNotificationOut(
            id=n.id, email_uid=n.email_uid, sender=n.sender,
            subject=n.subject, body_snippet=n.body_snippet,
            ai_reason=n.ai_reason, triggered_word=n.triggered_word,
            action_url=n.action_url, created_at=n.created_at,
        )
        for n in pending
    ]


# ============= Device tokens (FCM push) =============

@router.post("/profile/device-token", status_code=status.HTTP_204_NO_CONTENT, tags=["profile"])
async def register_device_token(
    body: DeviceTokenRequest,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Register an FCM device token for push notifications."""
    await uc.user_repo.save_device_token(user_id, body.token, body.platform)


# ============= Keywords =============

@router.post("/keywords", response_model=UserOut, tags=["keywords"])
async def add_keyword(
    body: AddKeywordRequest,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        await uc.add_trigger_word(user_id, body.word)
    except ValueError:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    return await get_profile(user_id=user_id, uc=uc)


@router.post("/keywords/stop", response_model=UserOut, tags=["keywords"])
async def add_stop_word(
    body: AddStopWordRequest,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        await uc.add_stop_word(user_id, body.word)
    except ValueError:
        raise HTTPException(status_code=409, detail="Stop word already exists")
    return await get_profile(user_id=user_id, uc=uc)


@router.delete("/keywords/{word}", response_model=UserOut, tags=["keywords"])
async def remove_keyword(
    word: str,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    await uc.user_repo.remove_keyword(user_id, word)
    return await get_profile(user_id=user_id, uc=uc)


# ============= Email history & stats =============

@router.get("/emails/history", response_model=List[EmailHistoryItem], tags=["emails"])
async def get_email_history(
    limit: int = 10,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    history = await uc.get_email_history(user_id, limit=limit)
    return [EmailHistoryItem(**item) for item in history]


@router.get("/emails/stats", response_model=StatsOut, tags=["emails"])
async def get_stats(
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    stats = await uc.get_stats(user_id)
    return StatsOut(**stats)


# ============= WebSocket =============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
