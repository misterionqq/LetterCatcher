from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError, jwt
from sqlalchemy import text

from src.use_cases.manage_users import ManageUsersUseCase
from src.infrastructure.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, APP_MODE, CLIENT_MODE, EMAIL_USER,
    TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME, APP_BASE_URL,
)
from src.infrastructure.telegram_auth import verify_telegram_login
from src.infrastructure.database.setup import AsyncSessionLocal
from src.presentation.api.security import create_access_token, get_current_user_id
from src.presentation.api.dependencies import get_user_use_case, get_scanner
from src.presentation.api.ws_manager import ws_manager
from src.presentation.api.rate_limit import limiter
from src.presentation.api.schemas import (
    TokenRequest, WebRegisterRequest, WebLoginRequest, TokenResponse,
    UserOut, KeywordOut, SetEmailRequest, SetSensitivityRequest,
    AddKeywordRequest, AddStopWordRequest,
    DeviceTokenRequest,
    LinkTelegramResponse,
    ForgotPasswordRequest, ResetPasswordRequest, MessageResponse,
    EmailHistoryItem, StatsOut,
    DndToggleOut, PendingNotificationOut,
    HealthOut,
    ServerInfoOut,
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


@router.get("/settings/server-info", response_model=ServerInfoOut, tags=["system"])
async def server_info():
    """Public server configuration. No auth required."""
    return ServerInfoOut(
        app_mode=APP_MODE,
        client_mode=CLIENT_MODE,
        forwarding_email=EMAIL_USER if APP_MODE == "centralized" else None,
        bot_username=TELEGRAM_BOT_USERNAME or None,
    )


# ============= Auth =============

@router.post("/auth/web/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, tags=["auth"])
@limiter.limit("5/minute")
async def web_register(
    request: Request,
    body: WebRegisterRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Register a new user via email + password. Sends verification email."""
    try:
        user = await uc.register_web_user(body.email, body.password, base_url=APP_BASE_URL)
    except ValueError as e:
        detail = str(e)
        if detail == "email_taken":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/web/login", response_model=TokenResponse, tags=["auth"])
@limiter.limit("5/minute")
async def web_login(
    request: Request,
    body: WebLoginRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Login with email + password (web / mobile app)."""
    user = await uc.authenticate_web_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
@limiter.limit("3/minute")
async def get_token(
    request: Request,
    body: TokenRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Login via Telegram Login Widget (validates HMAC-SHA256 hash)."""
    login_data = body.model_dump()
    # Remove empty optional fields (Telegram omits them from hash calculation)
    login_data = {k: str(v) for k, v in login_data.items() if v}
    # Always keep required fields
    login_data["id"] = str(body.id)
    login_data["auth_date"] = str(body.auth_date)
    login_data["hash"] = body.hash

    if not TELEGRAM_BOT_TOKEN or not verify_telegram_login(login_data, TELEGRAM_BOT_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram login data")

    user = await uc.get_user_profile_by_tg_id(body.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not registered. Use the Telegram bot first.")
    return TokenResponse(access_token=create_access_token(user.id))


# ============= Email verification & Password reset =============

@router.get("/auth/verify-email", response_model=MessageResponse, tags=["auth"])
async def verify_email(
    token: str = Query(...),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Verify email address using the token from verification email."""
    success = await uc.verify_email(token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    return MessageResponse(message="Email verified successfully")


@router.get("/auth/verify-email-change", response_model=MessageResponse, tags=["auth"])
async def verify_email_change(
    token: str = Query(...),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Confirm email change using the token sent to the new address."""
    success = await uc.confirm_email_change(token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return MessageResponse(message="Email changed successfully")


@router.post("/auth/resend-verification", response_model=MessageResponse, tags=["auth"])
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Resend email verification link. Requires auth."""
    success = await uc.resend_verification(user_id, base_url=APP_BASE_URL)
    if not success:
        raise HTTPException(status_code=400, detail="Email already verified or not set")
    return MessageResponse(message="Verification email sent")


@router.post("/auth/forgot-password", response_model=MessageResponse, tags=["auth"])
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Request a password reset email. Always returns success (prevents email enumeration)."""
    await uc.request_password_reset(body.email, base_url=APP_BASE_URL)
    return MessageResponse(message="If this email is registered, a reset link has been sent")


@router.post("/auth/reset-password", response_model=MessageResponse, tags=["auth"])
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Reset password using the token from the reset email."""
    success = await uc.reset_password(body.token, body.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    return MessageResponse(message="Password reset successfully")


# ============= Profile =============

def _user_out(user) -> UserOut:
    return UserOut(
        telegram_id=user.telegram_id,
        email=user.email,
        email_verified=user.email_verified,
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


@router.put("/profile/email", response_model=MessageResponse, tags=["profile"])
async def set_email(
    body: SetEmailRequest,
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    try:
        if uc.token_repo and uc.email_sender:
            await uc.request_email_change(user_id, body.email, base_url=APP_BASE_URL)
            return MessageResponse(message="Verification email sent to the new address")
        else:
            await uc.set_email(user_id, body.email, base_url=APP_BASE_URL)
            return MessageResponse(message="Email updated (verification unavailable)")
    except ValueError as e:
        detail = str(e)
        if detail == "email_taken":
            raise HTTPException(status_code=409, detail="Email already in use")
        raise HTTPException(status_code=422, detail="Invalid email format")


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


# ============= Account linking =============

@router.post("/profile/link-telegram", response_model=LinkTelegramResponse, tags=["profile"])
async def link_telegram(
    user_id: int = Depends(get_current_user_id),
    uc: ManageUsersUseCase = Depends(get_user_use_case),
):
    """Generate a Telegram deep link for account linking."""
    user = await uc.get_user_profile(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.telegram_id:
        raise HTTPException(status_code=409, detail="Telegram already linked")
    try:
        token = await uc.create_web_link_token(user_id)
    except ValueError:
        raise HTTPException(status_code=503, detail="Linking unavailable")
    bot_username = TELEGRAM_BOT_USERNAME
    if not bot_username:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")
    link = f"https://t.me/{bot_username}?start=link_{token}"
    return LinkTelegramResponse(link=link)


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
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
