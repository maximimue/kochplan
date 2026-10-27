import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://kochplan:kochplan@localhost:5432/kochplan_test")
os.environ.update({"ENV": "dev", "DEV_LOGIN_ENABLED": "true", "ANTHROPIC_API_KEY": "", "JWT_SECRET": "test-secret-test-secret-test-secret"})

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from pydantic import TypeAdapter  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import IngredientIn, RecipeIn  # noqa: E402
from app.services.recipes import load_catalog, upsert_ingredients, upsert_recipe  # noqa: E402

SEED = Path(__file__).parent.parent / "seed"


@pytest.fixture(scope="session", autouse=True)
async def database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        await upsert_ingredients(s, TypeAdapter(list[IngredientIn]).validate_python(json.loads((SEED / "ingredients.json").read_text())))
        cat = await load_catalog(s)
        for r in TypeAdapter(list[RecipeIn]).validate_python(json.loads((SEED / "recipes.json").read_text())):
            await upsert_recipe(s, r, catalog=cat)
        await s.commit()
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


_counter = 0


@pytest.fixture
async def user(client):
    """Frischer Nutzer je Test, liefert Auth-Header."""
    global _counter
    _counter += 1
    r = await client.post("/v1/auth/dev", json={"email": f"user{_counter}@test.local"})
    assert r.status_code == 200, r.text
    tok = r.json()
    return {"headers": {"Authorization": f"Bearer {tok['access_token']}"}, "tokens": tok}
