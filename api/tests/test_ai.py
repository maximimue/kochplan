import json

import httpx
import pytest

from app.config import Settings
from app.main import app
from app.services.ai import AiService, get_ai_service

AI_RECIPE = {
    "title": "Kürbis-Kokos-Suppe", "summary": "Herbstlich.", "servings": 2,
    "prep_minutes": 10, "cook_minutes": 20, "passive_minutes": 0,
    "kcal": 450, "protein_g": 8, "fat_g": 25, "carbs_g": 40,
    "appliances": ["herd"], "allergens": [], "tags": ["vegan"], "meal_types": ["abend"],
    "ingredients": [{"name": "Kokosmilch", "quantity": 200, "unit": "ml"}, {"name": "Hokkaido", "quantity": 800, "unit": "g"}],
    "steps": [{"text": "Alles kochen und pürieren.", "minutes": 25, "appliance": "herd"}],
    "cost_cents_per_serving": {"discount": 150, "standard": 190, "bio": 290},
}


def make_service(payload: dict, **settings):
    calls = []

    def handler(request: httpx.Request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "```json\n" + json.dumps(payload) + "\n```"}],
            "usage": {"input_tokens": 1000, "output_tokens": 800},
        })

    s = Settings(anthropic_api_key="test", **settings)
    return AiService(s, transport=httpx.MockTransport(handler)), calls


@pytest.fixture
def use_ai():
    def _use(svc):
        app.dependency_overrides[get_ai_service] = lambda: svc
    yield _use
    app.dependency_overrides.clear()


async def test_generate_ai_recipe(client, user, use_ai):
    svc, calls = make_service(AI_RECIPE)
    use_ai(svc)
    await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["herd"], "allergens": ["gluten"]})
    r = await client.post("/v1/recipes/generate", headers=user["headers"], json={"meal": "abend", "wish": "Kürbis"})
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "ai"
    prompt = calls[0]["messages"][0]["content"]
    assert "gluten" in prompt and "Kürbis" in prompt
    # nur für den Ersteller sichtbar
    rid = r.json()["id"]
    assert (await client.get(f"/v1/recipes/{rid}", headers=user["headers"])).status_code == 200


async def test_ai_recipe_violating_allergens_rejected(client, user, use_ai):
    bad = {**AI_RECIPE, "allergens": ["sesam"]}
    svc, _ = make_service(bad)
    use_ai(svc)
    await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["herd"], "allergens": ["sesam"]})
    r = await client.post("/v1/recipes/generate", headers=user["headers"], json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ai_constraint_violation"


async def test_ai_rate_limit(client, user, use_ai):
    svc, _ = make_service(AI_RECIPE, ai_rate_per_minute=2)
    use_ai(svc)
    await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["herd"]})
    codes = [(await client.post("/v1/recipes/generate", headers=user["headers"], json={})).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


async def test_monthly_limit_when_enabled(client, user, use_ai):
    svc, _ = make_service(AI_RECIPE, ai_limits_enabled=True)
    use_ai(svc)
    await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["herd"]})
    # MVP-Abo: unbegrenzt
    assert (await client.post("/v1/recipes/generate", headers=user["headers"], json={})).status_code == 201


async def test_plan_fills_gaps_with_ai(client, user, use_ai):
    svc, calls = make_service(AI_RECIPE)
    use_ai(svc)
    await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["herd"]})
    slots = [{"date": f"2026-11-0{2 + i}", "meal": "abend", "eat_at": "19:00"} for i in range(3)]
    r = await client.post("/v1/plans/generate", headers=user["headers"], json={"week_start": "2026-11-02", "slots": slots})
    titles = [e["recipe_title"] for e in r.json()["entries"]]
    assert titles.count("Kürbis-Kokos-Suppe") == 2 and len(calls) == 2
