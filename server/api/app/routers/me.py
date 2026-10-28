from fastapi import APIRouter

from app.auth.deps import CurrentUser, Session
from app.schemas import ProfileOut, ProfilePatch

router = APIRouter(prefix="/me", tags=["profil"])

# Felder, die per explizitem null (bzw. "" beim Fitnessziel) gelöscht werden dürfen.
CLEARABLE = {"weekly_budget_cents", "fitness_goal"}


@router.get("", response_model=ProfileOut, operation_id="getMe")
async def get_me(user: CurrentUser):
    return user


@router.patch("", response_model=ProfileOut, operation_id="updateMe")
async def patch_me(body: ProfilePatch, user: CurrentUser, session: Session):
    for key in body.model_fields_set:
        value = getattr(body, key)
        if value is not None or key in CLEARABLE:
            setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("", status_code=204, operation_id="deleteMe")
async def delete_me(user: CurrentUser, session: Session):
    """Konto-Löschung — Pflicht laut App-Store-Richtlinie 5.1.1(v) und DSGVO Art. 17.
    Persönliches hängt per ON DELETE CASCADE am User (Tokens, KI-Rezepte, Nutzungslog). Der Haushalt
    samt Plänen wird nur gelöscht, wenn niemand sonst mehr darin ist.
    TODO Production: Apple-Token per /auth/revoke bei Apple widerrufen."""
    household = user.household
    others = [m for m in household.members if m.id != user.id]
    await session.delete(user)
    await session.flush()
    if others:
        household.household_size = max(len(others), household.household_size - 1)
    else:
        await session.delete(household)
    await session.commit()
