import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from app.auth.deps import CurrentUser, Session
from app.errors import AppError
from app.models import Recipe
from app.schemas import AiRecipeRequest, RecipeOut, RecipeSyncOut
from app.services.ai import AiService, get_ai_service
from app.services.household import constraints_for
from app.services.planner import visible_recipes as _visible

router = APIRouter(prefix="/recipes", tags=["rezepte"])


@router.get("/sync", response_model=RecipeSyncOut, operation_id="syncRecipes")
async def sync(user: CurrentUser, session: Session, since: dt.datetime | None = None):
    """Delta-Sync für den Offline-Cache der iOS-App (SwiftData).
    Erster Aufruf ohne `since` = Vollabgleich. Danach `since` = letztes `server_time`."""
    server_time = dt.datetime.now(dt.UTC)
    stmt = select(Recipe).where(_visible(user))
    if since is not None:
        stmt = stmt.where(Recipe.updated_at > since)
    rows = (await session.scalars(stmt.order_by(Recipe.updated_at))).all()
    return RecipeSyncOut(
        server_time=server_time,
        recipes=[r for r in rows if r.deleted_at is None],
        deleted_ids=[r.id for r in rows if r.deleted_at is not None] if since else [],
    )


@router.get("", response_model=list[RecipeOut], operation_id="listRecipes")
async def list_recipes(
    user: CurrentUser, session: Session,
    q: str | None = None, meal: str | None = None,
    max_minutes: Annotated[int | None, Query(ge=1)] = None,
    only_suitable: bool = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: int = 0,
):
    stmt = select(Recipe).where(_visible(user), Recipe.deleted_at.is_(None))
    if q:
        stmt = stmt.where(Recipe.title.ilike(f"%{q}%"))
    if meal:
        stmt = stmt.where(or_(Recipe.meal_types == [], Recipe.meal_types.any(meal)))
    if max_minutes:
        stmt = stmt.where(Recipe.prep_minutes + Recipe.cook_minutes + Recipe.passive_minutes <= max_minutes)
    if only_suitable:
        c = constraints_for(user)
        stmt = stmt.where(Recipe.appliances.contained_by(c.appliances))
        if c.allergens:
            stmt = stmt.where(~Recipe.allergens.overlap(c.allergens))
    return (await session.scalars(stmt.order_by(Recipe.title).limit(limit).offset(offset))).all()


@router.get("/{recipe_id}", response_model=RecipeOut, operation_id="getRecipe")
async def get_recipe(recipe_id: uuid.UUID, user: CurrentUser, session: Session):
    r = await session.scalar(select(Recipe).where(Recipe.id == recipe_id, _visible(user)))
    if r is None:
        raise AppError("not_found", 404, what="Rezept")
    return r


@router.post("/generate", response_model=RecipeOut, status_code=201, operation_id="generateRecipe")
async def generate(
    body: AiRecipeRequest, user: CurrentUser, session: Session,
    ai: Annotated[AiService, Depends(get_ai_service)],
):
    return await ai.generate_recipe(session, user, meal=body.meal, wish=body.wish)
