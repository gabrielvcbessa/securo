import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication import JWTStrategy
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_active_user, get_user_manager
from app.core.config import get_settings
from app.core.database import get_async_session
from app.core.rate_limit import login_rate_limit
from app.models.mobile_session import MobileSession
from app.models.passkey import UserPasskey
from app.models.user import User
from app.schemas.mobile_auth import (
    MobileLoginRequest,
    MobileSessionRead,
    MobileTokenResponse,
    RefreshRequest,
)

router = APIRouter(prefix="/api/auth/mobile", tags=["mobile-auth"])
settings = get_settings()


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _mobile_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key.get_secret_value(),
        lifetime_seconds=settings.mobile_access_token_expire_minutes * 60,
    )


async def _issue_session(
    session: AsyncSession, user: User, device_name: str
) -> MobileTokenResponse:
    now = _utcnow()
    raw_refresh_token = secrets.token_urlsafe(48)
    mobile_session = MobileSession(
        user_id=user.id,
        token_hash=_hash_token(raw_refresh_token),
        device_name=device_name,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=settings.mobile_refresh_token_expire_days),
    )
    session.add(mobile_session)
    await session.flush()
    access_token = await _mobile_strategy().write_token(user)
    return MobileTokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        expires_in=settings.mobile_access_token_expire_minutes * 60,
        refresh_expires_in=settings.mobile_refresh_token_expire_days * 86400,
        session_id=mobile_session.id,
    )


@router.post(
    "/login",
    response_model=MobileTokenResponse,
    dependencies=[Depends(login_rate_limit)],
)
async def mobile_login(
    body: MobileLoginRequest,
    user_manager=Depends(get_user_manager),
    session: AsyncSession = Depends(get_async_session),
):
    credentials = OAuth2PasswordRequestForm(username=body.email, password=body.password)
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise _error(401, "INVALID_CREDENTIALS", "Email or password is incorrect")

    if user.is_2fa_enabled and user.totp_secret:
        if not body.totp_code:
            raise _error(401, "TOTP_REQUIRED", "A TOTP code is required")
        if not pyotp.TOTP(user.totp_secret).verify(body.totp_code):
            raise _error(401, "INVALID_TOTP", "The TOTP code is invalid")
    elif await session.scalar(
        select(UserPasskey.id).where(UserPasskey.user_id == user.id).limit(1)
    ):
        raise _error(
            409,
            "PASSKEY_FLOW_REQUIRED",
            "This account requires passkey authentication, which is not available in this flow",
        )

    response = await _issue_session(session, user, body.device_name.strip())
    await session.commit()
    return response


@router.post(
    "/refresh",
    response_model=MobileTokenResponse,
    dependencies=[Depends(login_rate_limit)],
)
async def refresh_mobile_session(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
):
    now = _utcnow()
    token_hash = _hash_token(body.refresh_token)
    mobile_session = await session.scalar(
        select(MobileSession).where(MobileSession.token_hash == token_hash)
    )
    if (
        mobile_session is None
        or mobile_session.revoked_at is not None
        or _as_utc(mobile_session.expires_at) <= now
    ):
        raise _error(401, "INVALID_REFRESH_TOKEN", "The refresh token is invalid or expired")

    claim = await session.execute(
        update(MobileSession)
        .where(MobileSession.id == mobile_session.id, MobileSession.revoked_at.is_(None))
        .values(revoked_at=now, last_used_at=now)
    )
    if claim.rowcount != 1:
        await session.rollback()
        raise _error(401, "REFRESH_TOKEN_REUSED", "The refresh token has already been used")

    user = await session.get(User, mobile_session.user_id)
    if user is None or not user.is_active:
        await session.rollback()
        raise _error(401, "INACTIVE_USER", "The user is no longer active")

    response = await _issue_session(session, user, mobile_session.device_name)
    mobile_session.replaced_by_id = response.session_id
    await session.commit()
    return response


@router.post("/logout")
async def logout_mobile_session(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
):
    await session.execute(
        update(MobileSession)
        .where(
            MobileSession.token_hash == _hash_token(body.refresh_token),
            MobileSession.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )
    await session.commit()
    return {"detail": "Logged out"}


@router.get("/sessions", response_model=list[MobileSessionRead])
async def list_mobile_sessions(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return list(
        (
            await session.scalars(
                select(MobileSession)
                .where(MobileSession.user_id == user.id)
                .order_by(MobileSession.created_at.desc())
            )
        ).all()
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_mobile_session(
    session_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await session.execute(
        update(MobileSession)
        .where(MobileSession.id == session_id, MobileSession.user_id == user.id)
        .values(revoked_at=_utcnow())
    )
    await session.commit()


@router.post("/logout-all")
async def logout_all_mobile_sessions(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await session.execute(
        update(MobileSession)
        .where(MobileSession.user_id == user.id, MobileSession.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )
    await session.commit()
    return {"detail": "All mobile sessions logged out"}
