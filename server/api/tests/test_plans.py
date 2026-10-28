import datetime as dt

WEEK = "2026-11-02"


def slots(n, meal="abend"):
    return [{"date": f"2026-11-0{2 + i}", "meal": meal, "eat_at": "19:00"} for i in range(n)]


async def setup_profile(client, user, **extra):
    body = {"appliances": ["herd", "backofen"], "supermarket": "lidl", "household_size": 2, **extra}
    r = await client.patch("/v1/me", headers=user["headers"], json=body)
    assert r.status_code == 200, r.text


async def test_plan_respects_appliances_and_start_time(client, user):
    await setup_profile(client, user)
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": WEEK, "slots": slots(2), "seed": 1})
    assert r.status_code == 200, r.text
    plan = r.json()
    titles = {e["recipe_title"] for e in plan["entries"]}
    assert titles == {"Ofen-Süßkartoffeln mit Kichererbsen und Zitronen-Tahin", "Rote-Linsen-Curry mit Kokosmilch und Spinat"}
    for e in plan["entries"]:
        start = dt.datetime.fromisoformat(e["start_at"])
        eat = dt.datetime.fromisoformat(f"{e['date']}T19:00:00+01:00")
        assert eat - start == dt.timedelta(minutes=e["total_minutes"] + 10)
    assert plan["total_cost_cents"] > 0


async def test_plan_excludes_allergens(client, user):
    await setup_profile(client, user, allergens=["sesam"])
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": WEEK, "slots": slots(1), "seed": 3, "use_ai": False})
    assert r.json()["entries"][0]["recipe_title"].startswith("Rote-Linsen")


async def test_plan_gap_without_ai_repeats_with_warning(client, user):
    await setup_profile(client, user)
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": WEEK, "slots": slots(3), "use_ai": True})
    codes = [w["code"] for w in r.json()["warnings"]]
    assert "ai_skipped" in codes and "recipe_repeated" in codes
    assert all(e["recipe_id"] for e in r.json()["entries"])


async def test_budget_warning(client, user):
    await setup_profile(client, user, weekly_budget_cents=100)
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": WEEK, "slots": slots(2), "use_ai": False})
    plan = r.json()
    assert plan["over_budget"] is True
    assert any(w["code"] == "over_budget" for w in plan["warnings"])


async def test_pescetarian_also_gets_vegetarian_recipes(client, user):
    await setup_profile(client, user, diet_tags=["pescetarisch"])
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": WEEK, "slots": slots(1), "use_ai": False})
    assert r.json()["entries"][0]["recipe_id"] is not None
    assert not any(w["code"] == "no_matching_recipes" for w in r.json()["warnings"])


async def test_breakfast_slot_uses_breakfast_recipe(client, user):
    await setup_profile(client, user)
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": WEEK, "slots": slots(1, "fruehstueck"), "use_ai": False})
    assert r.json()["entries"][0]["recipe_title"] == "Overnight Oats mit Heidelbeeren"


async def test_sync_lww_conflict(client, user):
    await setup_profile(client, user)
    gen = (await client.post("/v1/plans/generate", headers=user["headers"],
                             json={"week_start": WEEK, "slots": slots(1), "use_ai": False})).json()
    stale = {"client_updated_at": "2020-01-01T00:00:00Z", "entries": []}
    r = await client.put(f"/v1/plans/{WEEK}", headers=user["headers"], json=stale)
    assert r.status_code == 409
    assert r.json()["server_version"]["id"] == gen["id"]

    newer = {"client_updated_at": dt.datetime.now(dt.UTC).isoformat(),
             "entries": [{"date": "2026-11-05", "meal": "abend", "eat_at": "18:00", "servings": 2,
                          "recipe_id": gen["entries"][0]["recipe_id"]}]}
    r = await client.put(f"/v1/plans/{WEEK}", headers=user["headers"], json=newer)
    assert r.status_code == 200
    assert r.json()["entries"][0]["date"] == "2026-11-05"
    assert r.json()["entries"][0]["start_at"] is not None


async def test_soft_delete_visible_in_delta_sync(client, user):
    await setup_profile(client, user)
    await client.post("/v1/plans/generate", headers=user["headers"], json={"week_start": WEEK, "slots": slots(1), "use_ai": False})
    since = (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)).isoformat()
    assert (await client.delete(f"/v1/plans/{WEEK}", headers=user["headers"])).status_code == 204
    r = await client.get("/v1/plans", headers=user["headers"], params={"since": since})
    assert r.json()[0]["deleted"] is True


async def test_recipe_sync(client, user):
    r = await client.get("/v1/recipes/sync", headers=user["headers"])
    body = r.json()
    assert len(body["recipes"]) == 4
    r2 = await client.get("/v1/recipes/sync", headers=user["headers"], params={"since": body["server_time"]})
    assert r2.json()["recipes"] == []
