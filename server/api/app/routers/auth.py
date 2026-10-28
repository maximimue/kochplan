from fastapi import APIRouter
from sqlalchemy import select

from app.auth.deps import CurrentUser, Session
from app.auth.providers import VerifiedIdentity, verify_apple, verify_google
from app.auth.tokens import create_access_token, issue_refresh_token, revoke, revoke_all, rotate_refresh_token
from app.config import get_settings
from app.errors import AppError
from app.models import AuthIdentity, Household, Subscription, User
from app.schemas import AppleLoginIn, DevLoginIn, GoogleLoginIn, RefreshIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


async def _login(session: Session, ident: VerifiedIdentity, display_name: str | None = None) -> TokenOut:
    row = await session.scalar(
        select(AuthIdentity).where(AuthIdentity.provider == ident.provider, AuthIdentity.subject == ident.subject)
    )
    is_new = row is None
    if is_new:
        # Bewusst KEIN automatisches Verknüpfen über gleiche E-Mail (Account-Takeover-Risiko).
        user = User(email=ident.email, display_name=display_name, timezone=get_settings().default_timezone,
                    household=Household(household_size=1))
        user.identities.append(AuthIdentity(provider=ident.provider, subject=ident.subject, email=ident.email))
        user.subscription = Subscription(plan="mvp", ai_requests_per_month=None)
        session.add(user)
        await session.flush()
        user_id = user.id
    else:
        user_id = row.user_id
    refresh = await issue_refresh_token(session, user_id)
    await session.commit()
    access, ttl = create_access_token(user_id)
    return TokenOut(access_token=access, refresh_token=refresh, expires_in=ttl, user_id=user_id, is_new_user=is_new)


@router.post("/apple", response_model=TokenOut, operation_id="loginApple")
async def login_apple(body: AppleLoginIn, session: Session):
    return await _login(session, await verify_apple(body.id_token, body.raw_nonce), body.display_name)


@router.post("/google", response_model=TokenOut, operation_id="loginGoogle")
async def login_google(body: GoogleLoginIn, session: Session):
    return await _login(session, await verify_google(body.id_token))


@router.post("/dev", response_model=TokenOut, include_in_schema=False)
async def login_dev(body: DevLoginIn, session: Session):
    s = get_settings()
    if not (s.dev_login_enabled and s.env == "dev"):
        raise AppError("dev_login_disabled", 403)
    return await _login(session, VerifiedIdentity("dev", body.email.lower(), body.email.lower()))


@router.post("/refresh", response_model=TokenOut, operation_id="refreshToken")
async def refresh(body: RefreshIn, session: Session):
    user_id, new_refresh = await rotate_refresh_token(session, body.refresh_token)
    await session.commit()
    access, ttl = create_access_token(user_id)
    return TokenOut(access_token=access, refresh_token=new_refresh, expires_in=ttl, user_id=user_id)


@router.post("/logout", status_code=204, operation_id="logout")
async def logout(body: RefreshIn, session: Session):
    await revoke(session, body.refresh_token)
    await session.commit()


@router.post("/logout-all", status_code=204, operation_id="logoutAll")
async def logout_all(user: CurrentUser, session: Session):
    await revoke_all(session, user.id)
    await session.commit()
