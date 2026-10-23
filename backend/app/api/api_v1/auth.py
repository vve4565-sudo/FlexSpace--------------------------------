import hashlib
import logging
import secrets
from pathlib import Path
from typing import Annotated
from uuid import UUID

from authx import TokenPayload
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from pydantic import EmailStr
from redis.exceptions import RedisError

from ...config.config import settings
from ...config.security import security, verify_password
from ...crud import user as crud_user
from ...database.db import SessionDep
from ...database.models import UserStatus
from ...redis_client import redis
from ...shemas.booking import STokenResponse
from ...shemas.user import SOutputUser, SUserCreate, SUserLogin
from ...utils.email import generate_password_recovery_template, send_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_RESET_PAGE = Path(__file__).resolve().parents[4] / "frontend" / "reset_password.html"


def _token_key(namespace: str, token: str) -> str:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"auth:{namespace}:{token_hash}"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.JWT_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=int(settings.REFRESH_TOKEN_EXPIRE_DAYS.total_seconds()),
        path="/api/v1/auth",
    )


async def _issue_tokens(response: Response, user_id: UUID) -> STokenResponse:
    access_token = security.create_access_token(str(user_id))
    refresh_token = security.create_refresh_token(str(user_id))
    refresh_key = _token_key("refresh", refresh_token)
    refresh_seconds = int(settings.REFRESH_TOKEN_EXPIRE_DAYS.total_seconds())
    try:
        stored = await redis.set(
            refresh_key, str(user_id), ex=refresh_seconds, nx=True
        )
        if not stored:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    except RedisError as error:
        logger.exception("Unable to store refresh token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error

    user_tokens_key = f"auth:user-refresh:{user_id}"
    try:
        await redis.sadd(user_tokens_key, refresh_key)
        await redis.expire(user_tokens_key, refresh_seconds)
    except RedisError as error:
        await redis.delete(refresh_key)
        logger.exception("Unable to index refresh token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error

    _set_refresh_cookie(response, refresh_token)
    return STokenResponse(access_token=access_token)


async def _apply_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    script = """
    local count = redis.call('INCR', KEYS[1])
    if count == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    return count
    """
    try:
        count = await redis.eval(script, 1, key, window_seconds)
    except RedisError as error:
        logger.exception("Authentication rate limiter unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, try again later",
            headers={"Retry-After": str(window_seconds)},
        )


@router.post(
    "/registration",
    status_code=status.HTTP_201_CREATED,
    response_model=STokenResponse,
)
async def registration(
    session: SessionDep,
    response: Response,
    credentials: Annotated[SUserCreate, Form()],
) -> STokenResponse:
    user = await crud_user.get_user_by_email(session, str(credentials.email))
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )

    new_user = await crud_user.create_user(session, credentials)
    tokens = await _issue_tokens(response, new_user.id)
    logger.info("User registered user_id=%s", new_user.id)
    return tokens


@router.post("/login", response_model=STokenResponse)
async def login(
    session: SessionDep,
    response: Response,
    credentials: Annotated[SUserLogin, Form()],
) -> STokenResponse:
    user = await crud_user.get_user_by_email(session, str(credentials.email))
    if user is None or user.status is not UserStatus.active:
        verify_password(credentials.password, dummyhash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    valid_password, replacement_hash = verify_password(
        credentials.password, user.password_hash
    )
    if not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if replacement_hash:
        user.password_hash = replacement_hash
        await session.flush()

    tokens = await _issue_tokens(response, user.id)
    logger.info("User authenticated user_id=%s", user.id)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    refresh_token = request.cookies.get(settings.JWT_REFRESH_COOKIE_NAME)
    if refresh_token:
        key = _token_key("refresh", refresh_token)
        try:
            user_id = await redis.getdel(key)
            if user_id:
                await redis.srem(f"auth:user-refresh:{user_id}", key)
        except RedisError as error:
            logger.exception("Unable to revoke refresh token")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable",
            ) from error
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


@router.post("/refresh", response_model=STokenResponse)
async def refresh(response: Response, request: Request) -> STokenResponse:
    refresh_token = request.cookies.get(settings.JWT_REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required"
        )

    try:
        payload: TokenPayload = security.verify_token(refresh_token, verify_type=True)
        user_id = UUID(payload.sub)
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from error

    old_key = _token_key("refresh", refresh_token)
    try:
        stored_user_id = await redis.getdel(old_key)
        if stored_user_id:
            await redis.srem(f"auth:user-refresh:{stored_user_id}", old_key)
    except RedisError as error:
        logger.exception("Unable to rotate refresh token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error
    if stored_user_id != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    tokens = await _issue_tokens(response, user_id)
    logger.info("Refresh token rotated user_id=%s", user_id)
    return tokens


@router.post("/forgot_password")
async def forgot_password(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    request: Request,
    email: Annotated[EmailStr, Form()],
) -> dict[str, str]:
    client = request.client.host if request.client else "unknown"
    client_hash = hashlib.sha256(client.encode("utf-8")).hexdigest()
    email_hash = hashlib.sha256(str(email).lower().encode("utf-8")).hexdigest()
    await _apply_rate_limit(f"auth:reset-limit:ip:{client_hash}", 5, 900)
    await _apply_rate_limit(f"auth:reset-limit:email:{email_hash}", 5, 900)

    user = await crud_user.get_user_by_email(session, str(email))
    if user and user.status is UserStatus.active:
        token = secrets.token_urlsafe(32)
        key = _token_key("password-reset", token)
        try:
            await redis.set(key, str(user.id), ex=900, nx=True)
        except RedisError as error:
            logger.exception("Unable to create password reset token")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password recovery is temporarily unavailable",
            ) from error

        if settings.emails_enabled:
            background_tasks.add_task(
                send_email,
                str(email),
                "Password recovery",
                generate_password_recovery_template(token),
            )
        else:
            logger.error("Password recovery requested while email is not configured")

    return {"message": "If the account exists, a recovery email will be sent"}


@router.get("/reset_password")
async def reset_password() -> FileResponse:
    return FileResponse(
        _RESET_PAGE,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post("/reset_password", status_code=status.HTTP_200_OK)
async def create_password(
    session: SessionDep,
    request: Request,
    token: str,
    password: Annotated[str, Form(min_length=12, max_length=128)],
    password_confirm: Annotated[str, Form(min_length=12, max_length=128)],
) -> dict[str, str]:
    client = request.client.host if request.client else "unknown"
    client_hash = hashlib.sha256(client.encode("utf-8")).hexdigest()
    await _apply_rate_limit(f"auth:reset-attempt:ip:{client_hash}", 10, 900)
    if password != password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match"
        )

    try:
        user_id_value = await redis.getdel(_token_key("password-reset", token))
    except RedisError as error:
        logger.exception("Unable to consume password reset token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery is temporarily unavailable",
        ) from error
    if user_id_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    user_id = UUID(user_id_value)
    if not await crud_user.update_password(session, password, user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    try:
        refresh_keys = await redis.smembers(f"auth:user-refresh:{user_id}")
        if refresh_keys:
            await redis.delete(*refresh_keys)
        await redis.delete(f"auth:user-refresh:{user_id}")
    except RedisError as error:
        logger.exception("Unable to revoke sessions after password reset")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password changed but session revocation failed",
        ) from error
    logger.info("Password reset completed user_id=%s", user_id)
    return {"message": "Password updated"}
