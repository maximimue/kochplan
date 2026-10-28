import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.auth.deps import CurrentUser, Locale, Session
from app.config import get_settings
from app.errors import AppError
from app.i18n import t
from app.models import MealPlan, PlanEntry, Recipe
from app.schemas import GeneratePlanIn, PlanOut, PlanPutIn
from app.services.ai import AiService, get_ai_service
from app.services.household import assign_portions
from app.services.planner import generate_plan, serialize_plan
from app.services.schedule import compute_start_at

router = APIRouter(prefix="/plans", tags=["pläne"])


async def _get_plan(session, user, week_start: dt.date) -> MealPlan | None:
    return await session.scalar(
        select(MealPlan).where(MealPlan.household_id == user.household_id, MealPlan.week_start == week_start)
    )


@router.post("/generate", response_model=PlanOut, operation_id="generatePlan")
async def generate(
    body: GeneratePlanIn, user: CurrentUser, session: Session, locale: Locale,
    ai: Annotated[AiService, Depends(get_ai_service)],
):
    plan, warnings = await generate_plan(session, user, body, ai)
    return serialize_plan(plan, user, warnings, locale)


@router.get("", response_model=list[PlanOut], operation_id="listPlans")
async def list_plans(user: CurrentUser, session: Session, locale: Locale, since: dt.datetime | None = None):
    """Delta-Sync: mit `since` auch gelöschte Pläne (deleted=true)."""
    stmt = select(MealPlan).where(MealPlan.household_id == user.household_id)
    if since:
        stmt = stmt.where(MealPlan.updated_at > since)
    else:
        stmt = stmt.where(MealPlan.deleted_at.is_(None))
    plans = (await session.scalars(stmt.order_by(MealPlan.week_start))).all()
    return [serialize_plan(p, user, [], locale) for p in plans]


@router.get("/{week_start}", response_model=PlanOut, operation_id="getPlan")
async def get_plan(week_start: dt.date, user: CurrentUser, session: Session, locale: Locale):
    plan = await _get_plan(session, user, week_start)
    if plan is None or plan.deleted_at is not None:
        raise AppError("not_found", 404, what="Plan")
    return serialize_plan(plan, user, [], locale)


@router.put("/{week_start}", response_model=PlanOut, operation_id="upsertPlan")
async def put_plan(week_start: dt.date, body: PlanPutIn, user: CurrentUser, session: Session, locale: Locale):
    """Offline-Änderungen hochladen. Last-Write-Wins über client_updated_at:
    ist die Server-Version neuer, kommt 409 mit der Server-Version zurück."""
    plan = await _get_plan(session, user, week_start)
    if plan is not None and plan.client_updated_at > body.client_updated_at:
        return JSONResponse(status_code=409, content={
            "error": {"code": "sync_conflict", "message": t("errors.sync_conflict", locale)},
            "server_version": serialize_plan(plan, user, [], locale).model_dump(mode="json"),
        })
    if plan is None:
        plan = MealPlan(household_id=user.household_id, week_start=week_start)
        session.add(plan)

    ids = {e.recipe_id for e in body.entries if e.recipe_id}
    recipes = {r.id: r for r in (await session.scalars(select(Recipe).where(Recipe.id.in_(ids)))).all()} if ids else {}
    s = get_settings()
    portions = assign_portions(body.entries, [recipes.get(e.recipe_id) for e in body.entries], user.household)
    plan.deleted_at = None
    plan.client_updated_at = body.client_updated_at
    plan.entries = [
        PlanEntry(
            **({"id": e.id} if e.id else {}),
            date=e.date, meal=e.meal, eat_at=e.eat_at, portions=member_portions, total_portions=total,
            recipe_id=e.recipe_id if e.recipe_id in recipes else None,
            recipe=recipes.get(e.recipe_id),
            start_at=compute_start_at(e.date, e.eat_at, recipes[e.recipe_id].total_minutes, user.timezone,
                                      s.start_buffer_minutes) if e.recipe_id in recipes else None,
        )
        for e, (member_portions, total) in zip(body.entries, portions)
    ]
    await session.commit()
    await session.refresh(plan)
    return serialize_plan(plan, user, [], locale)


@router.delete("/{week_start}", status_code=204, operation_id="deletePlan")
async def delete_plan(week_start: dt.date, user: CurrentUser, session: Session):
    plan = await _get_plan(session, user, week_start)
    if plan is None:
        raise AppError("not_found", 404, what="Plan")
    plan.deleted_at = dt.datetime.now(dt.UTC)   # Soft-Delete, damit Offline-Clients es per Sync erfahren
    plan.client_updated_at = plan.deleted_at
    await session.commit()
