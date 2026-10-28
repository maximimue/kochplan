"""Plan-Generierung für einen Haushalt: feste DB zuerst, Lücken per KI, dann notfalls Wiederholungen.
Mit Fitnesszielen wird je Slot ein kcal-Ziel abgeleitet, die Auswahl darauf ausgerichtet und
jedem Mitglied eine eigene Portion zugeteilt."""
import datetime as dt
import random
import uuid
from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError, Warning_
from app.models import MealPlan, PlanEntry, Recipe, User
from app.schemas import GeneratePlanIn, PlanEntryOut, PlanOut, SlotIn
from app.services.ai import AiService
from app.services.fitness import Targets, targets_for
from app.services.household import assign_portions, constraints_for, reference_kcal_targets
from app.services.schedule import compute_start_at
from app.vocab import DIET_ACCEPTS, price_tier

PROTEIN_WEIGHT = 0.5      # Bonus je Anteil Protein-kcal an den Gesamt-kcal eines Rezepts
FITNESS_SHORTLIST = 5     # Zufall nur unter den besten n, damit der Plan abwechslungsreich bleibt
KCAL_TOLERANCE = 0.15
PROTEIN_MIN_SHARE = 0.8


def recipe_cost(recipe: Recipe | None, tier: str, portions: float) -> int | None:
    if recipe is None:
        return None
    per = recipe.cost_cents_per_serving.get(tier) or recipe.cost_cents_per_serving.get("standard")
    return None if per is None else round(per * portions)


def fits_meal(recipe: Recipe, meal: str) -> bool:
    return not recipe.meal_types or meal in recipe.meal_types


def visible_recipes(user: User):
    """Kuratierte Rezepte + KI-Rezepte aller Haushaltsmitglieder."""
    return or_(Recipe.source == "curated", Recipe.owner_user_id.in_([m.id for m in user.household.members]))


async def load_candidates(session: AsyncSession, user: User) -> list[Recipe]:
    c = constraints_for(user)
    stmt = select(Recipe).where(
        Recipe.deleted_at.is_(None), visible_recipes(user), Recipe.appliances.contained_by(c.appliances),
    )
    if c.allergens:
        stmt = stmt.where(~Recipe.allergens.overlap(c.allergens))
    for diet in c.diet_tags:
        stmt = stmt.where(Recipe.tags.overlap(sorted(DIET_ACCEPTS.get(diet, {diet}))))
    recipes = (await session.scalars(stmt)).all()
    if c.dislikes:
        recipes = [r for r in recipes if not any(d in i.name.lower() for d in c.dislikes for i in r.ingredients)]
    return list(recipes)


def fitness_score(recipe: Recipe, kcal_target: float) -> float:
    """Kleiner ist besser: relative kcal-Abweichung minus Bonus für Proteindichte."""
    if not recipe.kcal:
        return 2.0
    deviation = abs(recipe.kcal - kcal_target) / kcal_target
    protein_share = float(recipe.protein_g or 0) * 4 / recipe.kcal
    return deviation - PROTEIN_WEIGHT * protein_share


def pick(
    pool: list[Recipe], slot: SlotIn, portions: float, tier: str,
    remaining_budget: int | None, slots_left: int, rng: random.Random,
    kcal_target: float | None = None,
) -> Recipe | None:
    pool = [r for r in pool if fits_meal(r, slot.meal)]
    if not pool:
        return None
    if remaining_budget is not None:
        target = remaining_budget / max(slots_left, 1)
        affordable = [r for r in pool if (recipe_cost(r, tier, portions) or 0) <= target]
        pool = affordable or sorted(pool, key=lambda r: recipe_cost(r, tier, portions) or 0)[:3]
    if kcal_target is not None:
        pool = sorted(pool, key=lambda r: fitness_score(r, kcal_target))[:FITNESS_SHORTLIST]
    return rng.choice(pool)


def fitness_warnings(
    slots: list[SlotIn], picks: list[Recipe | None], my_portions: list[float], targets: Targets,
) -> list[Warning_]:
    """Ehrliches Feedback, wenn der Rezeptbestand die Ziele trotz Portionsanpassung nicht hergibt."""
    kcal_per_day: dict[dt.date, float] = defaultdict(float)
    protein_per_day: dict[dt.date, float] = defaultdict(float)
    for slot, r, portion in zip(slots, picks, my_portions):
        if r is not None:
            kcal_per_day[slot.date] += (r.kcal or 0) * portion
            protein_per_day[slot.date] += float(r.protein_g or 0) * portion
    if not kcal_per_day:
        return []
    warnings = []
    missed = sum(1 for k in kcal_per_day.values() if abs(k - targets.kcal) / targets.kcal > KCAL_TOLERANCE)
    if missed:
        warnings.append(Warning_("kcal_target_missed", days=missed, target=targets.kcal))
    avg_protein = sum(protein_per_day.values()) / len(protein_per_day)
    if avg_protein < PROTEIN_MIN_SHARE * targets.protein_g:
        warnings.append(Warning_("protein_target_missed", target=targets.protein_g,
                                 percent=round(100 * avg_protein / targets.protein_g)))
    return warnings


async def generate_plan(
    session: AsyncSession, user: User, body: GeneratePlanIn, ai: AiService
) -> tuple[MealPlan, list[Warning_]]:
    s = get_settings()
    household = user.household
    rng = random.Random(body.seed)
    tier = price_tier(household.supermarket)
    persons = household.household_size   # Schätzung fürs Budget, die echten Portionen stehen erst nach der Auswahl fest
    warnings: list[Warning_] = []
    if not household.appliances:
        warnings.append(Warning_("no_appliances"))

    candidates = await load_candidates(session, user)
    rng.shuffle(candidates)
    slots = sorted(body.slots, key=lambda x: (x.date, x.eat_at or dt.time(0)))
    picks: list[Recipe | None] = [None] * len(slots)
    used: set[uuid.UUID] = set()
    budget = household.weekly_budget_cents
    kcal_targets = reference_kcal_targets(slots, household)

    def spent() -> int:
        return sum(recipe_cost(r, tier, persons) or 0 for r in picks)

    # 1) Feste/gespeicherte Rezepte ohne Wiederholung
    for i, slot in enumerate(slots):
        remaining = None if budget is None else budget - spent()
        r = pick([c for c in candidates if c.id not in used], slot, persons, tier, remaining, len(slots) - i, rng,
                 kcal_targets[i])
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
                wish = f"ca. {round(kcal_targets[i])} kcal je Portion, möglichst proteinreich" if kcal_targets[i] else None
                try:
                    r = await ai.generate_recipe(session, user, meal=slots[i].meal, wish=wish, avoid_titles=titles)
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
            remaining = None if budget is None else budget - spent()
            r = pick(candidates, slot, persons, tier, remaining, 1, rng, kcal_targets[i])
            if r is None:
                warnings.append(Warning_("no_matching_recipes", date=slot.date.strftime("%d.%m."), meal=slot.meal))
            else:
                picks[i] = r
                warnings.append(Warning_("recipe_repeated", title=r.title))

    portions = assign_portions(slots, picks, household)
    if targets := targets_for(user):
        my_portions = [p.get(str(user.id), 1.0) for p, _ in portions]
        warnings.extend(fitness_warnings(slots, picks, my_portions, targets))

    plan = await session.scalar(
        select(MealPlan).where(MealPlan.household_id == household.id, MealPlan.week_start == body.week_start)
    )
    if plan is None:
        plan = MealPlan(household_id=household.id, week_start=body.week_start)
        session.add(plan)
    plan.deleted_at = None
    plan.client_updated_at = dt.datetime.now(dt.UTC)
    plan.entries = [
        PlanEntry(
            date=slot.date, meal=slot.meal, eat_at=slot.eat_at, portions=member_portions, total_portions=total,
            recipe_id=r.id if r else None, recipe=r,
            start_at=compute_start_at(slot.date, slot.eat_at, r.total_minutes, user.timezone, s.start_buffer_minutes) if r else None,
        )
        for slot, r, (member_portions, total) in zip(slots, picks, portions)
    ]
    await session.commit()
    await session.refresh(plan)
    return plan, warnings


def serialize_plan(plan: MealPlan, user: User, warnings: list[Warning_], locale: str) -> PlanOut:
    """Je anfragendem Mitglied: `my_portion` ist dessen eigene Portion, Kosten gelten für alle Portionen."""
    household = user.household
    tier = price_tier(household.supermarket)
    me = str(user.id)
    entries = []
    for e in plan.entries:
        total = float(e.total_portions)
        entries.append(PlanEntryOut(
            id=e.id, date=e.date, meal=e.meal, eat_at=e.eat_at,
            total_portions=total, my_portion=float(e.portions.get(me, 1.0)),
            recipe_id=e.recipe_id, recipe_title=e.recipe.title if e.recipe else None,
            total_minutes=e.recipe.total_minutes if e.recipe else None,
            start_at=e.start_at, cost_cents=recipe_cost(e.recipe, tier, total),
        ))
    total_cost = sum(x.cost_cents or 0 for x in entries)
    budget = household.weekly_budget_cents
    over = budget is not None and total_cost > budget
    if over and not any(w.code == "over_budget" for w in warnings):
        warnings = [*warnings, Warning_("over_budget", amount=f"{(total_cost - budget) / 100:.2f} €".replace(".", ","))]
    return PlanOut(
        id=plan.id, week_start=plan.week_start, entries=entries, total_cost_cents=total_cost,
        budget_cents=budget, over_budget=over, warnings=[w.render(locale) for w in warnings],
        updated_at=plan.updated_at, client_updated_at=plan.client_updated_at,
        deleted=plan.deleted_at is not None,
    )
