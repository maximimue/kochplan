from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.auth.tokens import decode_access_token
from app.db import get_session
from app.errors import AppError
from app.i18n import resolve_locale
from app.models import Household, User

Session = Annotated[AsyncSession, Depends(get_session)]


async def current_user(session: Session, authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthorized", 401)
    # Mitglieder explizit laden: die zyklische Eager-Kette User→Haushalt→Mitglieder bricht SQLAlchemy sonst ab,
    # und ein späteres Nachladen scheitert im async-Kontext.
    user = await session.get(
        User, decode_access_token(authorization[7:].strip()),
        options=[joinedload(User.household).selectinload(Household.members)],
    )
    if user is None:
        raise AppError("unauthorized", 401)
    return user


def locale(accept_language: Annotated[str | None, Header()] = None) -> str:
    return resolve_locale(accept_language)


CurrentUser = Annotated[User, Depends(current_user)]
Locale = Annotated[str, Depends(locale)]
