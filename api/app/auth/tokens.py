import datetime as dt
import hashlib
import secrets
import uuid

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.models import RefreshToken

ALGO = "HS256"
ISSUER = "kochplan-api"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    ttl = s.jwt_access_ttl_minutes * 60
    now = _now()
    payload = {"sub": str(user_id), "iss": ISSUER, "iat": now, "exp": now + dt.timedelta(seconds=ttl)}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGO), ttl


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGO], issuer=ISSUER)
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError("unauthorized", 401)


async def issue_refresh_token(session: AsyncSession, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(48)
    session.add(RefreshToken(
        user_id=user_id, token_hash=_hash(token),
        expires_at=_now() + dt.timedelta(days=get_settings().refresh_ttl_days),
    ))
    return token


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[uuid.UUID, str]:
    """Rotation mit Wiederverwendungs-Erkennung: wird ein bereits rotiertes Token erneut
    vorgelegt, werden alle Tokens des Users widerrufen (Token-Diebstahl wahrscheinlich)."""
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    if row is None:
        raise AppError("invalid_refresh_token", 401)
    if row.revoked_at is not None:
        await revoke_all(session, row.user_id)
        await session.commit()
        raise AppError("invalid_refresh_token", 401)
    if row.expires_at < _now():
        raise AppError("invalid_refresh_token", 401)
    row.revoked_at = _now()
    new = await issue_refresh_token(session, row.user_id)
    return row.user_id, new


async def revoke_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def revoke(session: AsyncSession, token: str) -> None:
    await session.execute(
        update(RefreshToken).where(RefreshToken.token_hash == _hash(token)).values(revoked_at=_now())
    )
