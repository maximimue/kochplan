import datetime as dt
import secrets

from fastapi import APIRouter
from sqlalchemy import select

from app.auth.deps import CurrentUser, Session
from app.errors import AppError
from app.models import Household, User
from app.schemas import HouseholdMemberOut, HouseholdOut, JoinHouseholdIn

router = APIRouter(prefix="/household", tags=["haushalt"])

INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # ohne 0/O/1/I/L — leicht vorzulesen
INVITE_LENGTH = 8                                      # ~39 Bit, zusammen mit kurzer Gültigkeit ausreichend
INVITE_TTL = dt.timedelta(hours=48)


def household_out(household: Household, user: User) -> HouseholdOut:
    return HouseholdOut(
        id=household.id,
        household_size=household.household_size,
        members=[
            HouseholdMemberOut(id=m.id, display_name=m.display_name, email=m.email, is_me=m.id == user.id,
                               has_fitness_goal=m.fitness_goal is not None)
            for m in household.members
        ],
        invite_code=household.invite_code if household.invite_expires_at and household.invite_expires_at > _now() else None,
        invite_expires_at=household.invite_expires_at,
    )


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@router.get("", response_model=HouseholdOut, operation_id="getHousehold")
async def get_household(user: CurrentUser):
    return household_out(user.household, user)


@router.post("/invite", response_model=HouseholdOut, operation_id="createHouseholdInvite")
async def create_invite(user: CurrentUser, session: Session):
    """Neuer Code ersetzt einen alten — so lässt sich ein weitergegebener Code entwerten."""
    h = user.household
    h.invite_code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))
    h.invite_expires_at = _now() + INVITE_TTL
    await session.commit()
    return household_out(h, user)


@router.post("/join", response_model=HouseholdOut, operation_id="joinHousehold")
async def join_household(body: JoinHouseholdIn, user: CurrentUser, session: Session):
    """Wechselt in den Haushalt des Codes. Ein bisheriger Ein-Personen-Haushalt wird samt seiner Pläne gelöscht."""
    code = body.code.strip().upper().replace("-", "").replace(" ", "")
    target = await session.scalar(
        select(Household).where(Household.invite_code == code, Household.invite_expires_at > _now())
    )
    if target is None:
        raise AppError("invite_invalid", 404)
    old = user.household
    if target.id != old.id:
        user.household = target
        target.household_size = max(target.household_size, len(target.members))
        await session.flush()
        if not old.members:
            await session.delete(old)
        else:
            old.household_size = max(len(old.members), old.household_size - 1)
        await session.commit()
    return household_out(target, user)


@router.post("/leave", response_model=HouseholdOut, operation_id="leaveHousehold")
async def leave_household(user: CurrentUser, session: Session):
    """Eigener neuer Haushalt mit den bisherigen Einstellungen als Startwert; die Pläne bleiben beim alten."""
    old = user.household
    if len(old.members) <= 1:
        return household_out(old, user)
    new = Household(supermarket=old.supermarket, weekly_budget_cents=old.weekly_budget_cents,
                    household_size=1, appliances=list(old.appliances))
    session.add(new)
    user.household = new
    await session.flush()
    old.household_size = max(len(old.members), old.household_size - 1)
    await session.commit()
    return household_out(new, user)
