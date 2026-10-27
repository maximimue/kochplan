"""Verwaltung: python -m app.cli <befehl> ...

  import-ingredients seed/ingredients.json
  import-recipes     seed/recipes.json [--dry-run]
  usage              [--month 2026-10]     KI-Kosten je Nutzer
"""
import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AiUsage, Recipe, User
from app.schemas import IngredientIn, RecipeIn
from app.services.recipes import load_catalog, slugify, upsert_ingredients, upsert_recipe


def _load(path: str, model):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        return TypeAdapter(list[model]).validate_python(raw)
    except ValidationError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


async def import_ingredients(path: str) -> None:
    items = _load(path, IngredientIn)
    async with SessionLocal() as s:
        rep = await upsert_ingredients(s, items)
        await s.commit()
    print(f"Zutaten: {rep.created} neu, {rep.updated} aktualisiert")


async def import_recipes(path: str, dry_run: bool) -> None:
    items = _load(path, RecipeIn)
    created = updated = 0
    warnings: list[str] = []
    async with SessionLocal() as s:
        catalog = await load_catalog(s)
        for item in items:
            exists = await s.scalar(select(Recipe.id).where(Recipe.slug == (item.slug or slugify(item.title))))
            _, w = await upsert_recipe(s, item, catalog=catalog)
            warnings += w
            updated += bool(exists)
            created += not exists
        if dry_run:
            await s.rollback()
        else:
            await s.commit()
    for w in warnings:
        print("WARNUNG:", w)
    print(f"Rezepte: {created} neu, {updated} aktualisiert{' (dry-run, nichts gespeichert)' if dry_run else ''}")


async def usage(month: str | None) -> None:
    start = dt.datetime.strptime(month, "%Y-%m").replace(tzinfo=dt.UTC) if month else \
        dt.datetime.now(dt.UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + dt.timedelta(days=32)).replace(day=1)
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(User.email, func.count(), func.sum(AiUsage.input_tokens), func.sum(AiUsage.output_tokens),
                   func.sum(AiUsage.cost_micro_usd))
            .join(User, User.id == AiUsage.user_id)
            .where(AiUsage.created_at >= start, AiUsage.created_at < end)
            .group_by(User.email)
        )).all()
    print(f"KI-Nutzung {start:%Y-%m}")
    for email, n, tin, tout, cost in rows:
        print(f"  {email or '-':35} {n:5} Req  {tin or 0:>9} in  {tout or 0:>9} out  ${(cost or 0) / 1e6:.2f}")


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import-ingredients").add_argument("path")
    r = sub.add_parser("import-recipes")
    r.add_argument("path")
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("usage").add_argument("--month")
    a = p.parse_args()
    if a.cmd == "import-ingredients":
        asyncio.run(import_ingredients(a.path))
    elif a.cmd == "import-recipes":
        asyncio.run(import_recipes(a.path, a.dry_run))
    else:
        asyncio.run(usage(a.month))


if __name__ == "__main__":
    main()
