from fastapi import APIRouter

from app.auth.deps import CurrentUser, Session
from app.schemas import ProfileOut, ProfilePatch

router = APIRouter(prefix="/me", tags=["profil"])


@router.get("", response_model=ProfileOut)
async def get_me(user: CurrentUser):
    return user


@router.patch("", response_model=ProfileOut)
async def patch_me(body: ProfilePatch, user: CurrentUser, session: Session):
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, key, value)
    if "weekly_budget_cents" in body.model_fields_set and body.weekly_budget_cents is None:
        user.weekly_budget_cents = None
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("", status_code=204)
async def delete_me(user: CurrentUser, session: Session):
    """Konto-Löschung — Pflicht laut App-Store-Richtlinie 5.1.1(v) und DSGVO Art. 17.
    Alles hängt per ON DELETE CASCADE am User (Pläne, Tokens, KI-Rezepte, Nutzungslog).
    TODO Production: Apple-Token per /auth/revoke bei Apple widerrufen."""
    await session.delete(user)
    await session.commit()
