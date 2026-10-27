"""Plan-Generierung: feste DB zuerst, Lücken per KI, dann notfalls Wiederholungen."""
import datetime as dt
import random
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError, Warning_
from app.models import MealPlan, PlanEntry, Recipe, User
from app.schemas import GeneratePlanIn, PlanEntryOut, PlanOut, SlotIn
from app.services.ai import AiService
from app.services.schedule import compute_start_at
from app.vocab import price_tier


def recipe_cost(recipe: Recipe | None, tier: str, servings: int) -> int | None:
    if recipe is None:
        return None
    per = recipe.cost_cents_per_serving.get(tier) or recipe.cost_cents_per_serving.get("standard")
    return None if per is None else per * servings


def fits_meal(recipe: Recipe, meal: str) -> bool:
    return not recipe.meal_types or meal in recipe.meal_types


async def load_candidates(session: AsyncSession, user: User) -> list[Recipe]:
    stmt = select(Recipe).where(
        Recipe.deleted_at.is_(None),
        or_(Recipe.source == "curated", Recipe.owner_user_id == user.id),
        Recipe.appliances.contained_by(user.appliances),
    )
    if user.allergens:
        stmt = stmt.where(~Recipe.allergens.overlap(user.allergens))
    if user.diet_tags:
        stmt = stmt.where(Recipe.tags.contains(user.diet_tags))
    recipes = (await session.scalars(stmt)).all()
    if user.dislikes:
        recipes = [
            r for r in recipes
            if not any(d in i.name.lower() for d in user.dislikes for i in r.ingredients)
        ]
    return list(recipes)


def pick(
    pool: list[Recipe], slot: SlotIn, servings: int, tier: str,
    remaining_budget: int | None, slots_left: int, rng: random.Random,
) -> Recipe | None:
    pool = [r for r in pool if fits_meal(r, slot.meal)]
    if not pool:
        return None
    if remaining_budget is not None:
        target = remaining_budget / max(slots_left, 1)
        affordable = [r for r in pool if (recipe_cost(r, tier, servings) or 0) <= target]
        pool = affordable or sorted(pool, key=lambda r: recipe_cost(r, tier, servings) or 0)[:3]
    return rng.choice(pool)


async def generate_plan(
    session: AsyncSession, user: User, body: GeneratePlanIn, ai: AiService
) -> tuple[MealPlan, list[Warning_]]:
    s = get_settings()
    rng = random.Random(body.seed)
    tier = price_tier(user.supermarket)
    warnings: list[Warning_] = []
    if not user.appliances:
        warnings.append(Warning_("no_appliances"))

    candidates = await load_candidates(session, user)
    rng.shuffle(candidates)
    slots = sorted(body.slots, key=lambda x: (x.date, x.eat_at or dt.time(0)))
    picks: list[Recipe | None] = [None] * len(slots)
    used: set[uuid.UUID] = set()
    budget = user.weekly_budget_cents

    def spent() -> int:
        return sum(recipe_cost(r, tier, sl.servings or user.household_size) or 0 for r, sl in zip(picks, slots))

    # 1) Feste/gespeicherte Rezepte ohne Wiederholung
    for i, slot in enumerate(slots):
        servings = slot.servings or user.household_size
        remaining = None if budget is None else budget - spent()
        r = pick([c for c in candidates if c.id not in used], slot, servings, tier, remaining, len(slots) - i, rng)
        if r is not None:
            picks[i] = r
            used.add(r.id)

    # 2) Lücken per KI füllen
    gaps = [i for i, r in enumerate(picks) if r is None]
    if gaps and body.use_ai:
        if not ai.available:
            warnings.append(Warning_("ai_skipped", reason="nicht konfiguriert"))
        else:
            titles = [r.title for r in picks if r] + [c.title for c in candidates[:20]]
            for n, i in enumerate(gaps):
                if n >= s.ai_max_per_plan:
                    warnings.append(Warning_("ai_skipped", reason="Maximum pro Plan erreicht"))
                    break
                try:
                    r = await ai.generate_recipe(session, user, meal=slots[i].meal, avoid_titles=titles)
                except AppError as e:
                    warnings.append(Warning_("ai_skipped", reason=e.code))
                    if e.code in ("ai_rate_limited", "ai_monthly_limit", "ai_unavailable"):
                        break
                    continue
                picks[i] = r
                titles.append(r.title)

    # 3) Restliche Lücken mit Wiederholungen füllen
    for i, slot in enumerate(slots):
        if picks[i] is None:
            servings = slot.servings or user.household_size
            remaining = None if budget is None else budget - spent()
            r = pick(candidates, slot, servings, tier, remaining, 1, rng)
            if r is None:
                warnings.append(Warning_("no_matching_recipes", date=slot.date.strftime("%d.%m."), meal=slot.meal))
            else:
                picks[i] = r
                warnings.append(Warning_("recipe_repeated", title=r.title))

    plan = await session.scalar(
        select(MealPlan).where(MealPlan.user_id == user.id, MealPlan.week_start == body.week_start)
    )
    if plan is None:
        plan = MealPlan(user_id=user.id, week_start=body.week_start)
        session.add(plan)
    plan.deleted_at = None
    plan.client_updated_at = dt.datetime.now(dt.UTC)
    plan.entries = [
        PlanEntry(
            date=slot.date, meal=slot.meal, eat_at=slot.eat_at,
            servings=slot.servings or user.household_size, recipe_id=r.id if r else None, recipe=r,
            start_at=compute_start_at(slot.date, slot.eat_at, r.total_minutes, user.timezone, s.start_buffer_minutes) if r else None,
        )
        for slot, r in zip(slots, picks)
    ]
    await session.commit()
    await session.refresh(plan)
    return plan, warnings


def serialize_plan(plan: MealPlan, user: User, warnings: list[Warning_], locale: str) -> PlanOut:
    tier = price_tier(user.supermarket)
    entries = []
    for e in plan.entries:
        entries.append(PlanEntryOut(
            id=e.id, date=e.date, meal=e.meal, eat_at=e.eat_at, servings=e.servings,
            recipe_id=e.recipe_id, recipe_title=e.recipe.title if e.recipe else None,
            total_minutes=e.recipe.total_minutes if e.recipe else None,
            start_at=e.start_at, cost_cents=recipe_cost(e.recipe, tier, e.servings),
        ))
    total = sum(x.cost_cents or 0 for x in entries)
    budget = user.weekly_budget_cents
    over = budget is not None and total > budget
    if over and not any(w.code == "over_budget" for w in warnings):
        warnings = [*warnings, Warning_("over_budget", amount=f"{(total - budget) / 100:.2f} €".replace(".", ","))]
    return PlanOut(
        id=plan.id, week_start=plan.week_start, entries=entries, total_cost_cents=total,
        budget_cents=budget, over_budget=over, warnings=[w.render(locale) for w in warnings],
        updated_at=plan.updated_at, client_updated_at=plan.client_updated_at,
        deleted=plan.deleted_at is not None,
    )
