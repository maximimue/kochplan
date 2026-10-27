import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ingredient, Recipe, RecipeIngredient
from app.schemas import IngredientIn, RecipeIn
from app.vocab import PRICE_TIERS, UNIT_CONVERSION


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def slugify(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:150]


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    warnings: list[str] = field(default_factory=list)


def calculate_cost(
    ingredients: list[RecipeIngredient], catalog: dict[str, Ingredient], servings: int
) -> tuple[dict[str, int], list[str]]:
    """Grobe Kosten je Portion pro Preis-Tier aus Zutatenkatalog. Keine Echtzeitpreise."""
    totals = {tier: 0.0 for tier in PRICE_TIERS}
    problems: list[str] = []
    for ri in ingredients:
        ing = catalog.get(normalize_name(ri.name))
        if ing is None:
            problems.append(f"Zutat nicht im Katalog: {ri.name}")
            continue
        if ri.quantity is None or ri.unit is None:
            continue
        base, factor = UNIT_CONVERSION[ri.unit]
        if base is None:
            continue
        if base != ing.base_unit:
            problems.append(f"Einheit {ri.unit} passt nicht zu {ing.name} ({ing.base_unit})")
            continue
        for tier in PRICE_TIERS:
            price = ing.prices.get(tier) or ing.prices.get("standard")
            if price is not None:
                totals[tier] += float(ri.quantity) * factor * price
    return {tier: round(v / servings) for tier, v in totals.items()}, problems


async def load_catalog(session: AsyncSession) -> dict[str, Ingredient]:
    return {i.name: i for i in (await session.scalars(select(Ingredient))).all()}


async def upsert_ingredients(session: AsyncSession, items: list[IngredientIn]) -> ImportReport:
    report = ImportReport()
    catalog = await load_catalog(session)
    for item in items:
        name = normalize_name(item.name)
        ing = catalog.get(name)
        if ing is None:
            session.add(Ingredient(name=name, base_unit=item.base_unit, prices=item.prices, allergens=item.allergens))
            report.created += 1
        else:
            ing.base_unit, ing.prices, ing.allergens = item.base_unit, item.prices, item.allergens
            report.updated += 1
    await session.flush()
    return report


async def upsert_recipe(
    session: AsyncSession, data: RecipeIn, *, source: str = "curated",
    owner_user_id=None, catalog: dict[str, Ingredient] | None = None,
) -> tuple[Recipe, list[str]]:
    catalog = catalog if catalog is not None else await load_catalog(session)
    slug = data.slug or slugify(data.title)
    if source == "ai":
        slug = f"ai-{slug[:120]}-{dt.datetime.now(dt.UTC).strftime('%y%m%d%H%M%S%f')}"
    recipe = await session.scalar(select(Recipe).where(Recipe.slug == slug))
    if recipe is None:
        recipe = Recipe(slug=slug, source=source, owner_user_id=owner_user_id)
        session.add(recipe)

    ris = [
        RecipeIngredient(
            ingredient_id=(catalog.get(normalize_name(i.name)).id if normalize_name(i.name) in catalog else None),
            name=i.name, quantity=i.quantity, unit=i.unit, note=i.note, position=pos,
        )
        for pos, i in enumerate(data.ingredients)
    ]
    computed, warnings = calculate_cost(ris, catalog, data.servings)
    # Allergene: deklarierte + aus Zutatenkatalog abgeleitete (Sicherheitsnetz gegen Lücken)
    derived = {a for i in data.ingredients if (c := catalog.get(normalize_name(i.name))) for a in c.allergens}

    recipe.title, recipe.summary, recipe.servings = data.title, data.summary, data.servings
    recipe.prep_minutes, recipe.cook_minutes, recipe.passive_minutes = data.prep_minutes, data.cook_minutes, data.passive_minutes
    recipe.kcal, recipe.protein_g, recipe.fat_g, recipe.carbs_g = data.kcal, data.protein_g, data.fat_g, data.carbs_g
    recipe.appliances = data.appliances
    recipe.allergens = sorted(set(data.allergens) | derived)
    recipe.tags, recipe.meal_types = data.tags, data.meal_types
    recipe.steps = [s.model_dump(exclude_none=True) for s in data.steps]
    recipe.cost_cents_per_serving = data.cost_cents_per_serving or computed
    recipe.ingredients = ris
    recipe.deleted_at = None
    await session.flush()
    return recipe, [f"{data.title}: {w}" for w in warnings] if not data.cost_cents_per_serving else []
