import datetime as dt

WEEK = "2026-11-02"
YEAR = dt.date.today().year


async def login(client, email):
    r = await client.post("/v1/auth/dev", json={"email": email})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def family(client, name):
    """Zwei Nutzer in einem Haushalt: a lädt ein, b tritt bei."""
    a, b = await login(client, f"{name}-a@test.local"), await login(client, f"{name}-b@test.local")
    await client.patch("/v1/me", headers=a, json={"appliances": ["herd", "backofen"], "supermarket": "lidl", "household_size": 1})
    code = (await client.post("/v1/household/invite", headers=a)).json()["invite_code"]
    r = await client.post("/v1/household/join", headers=b, json={"code": code.lower()})
    assert r.status_code == 200, r.text
    return a, b


def three_meals(days=2):
    return [{"date": f"2026-11-0{2 + d}", "meal": m, "eat_at": t}
            for d in range(days) for m, t in (("fruehstueck", "08:00"), ("mittag", "12:30"), ("abend", "18:30"))]


async def test_new_user_has_own_household(client, user):
    r = await client.get("/v1/household", headers=user["headers"])
    assert [m["is_me"] for m in r.json()["members"]] == [True]
    assert r.json()["invite_code"] is None


async def test_join_shares_settings_and_plans(client):
    a, b = await family(client, "share")
    hh = (await client.get("/v1/household", headers=b)).json()
    assert len(hh["members"]) == 2 and hh["household_size"] == 2
    assert (await client.get("/v1/me", headers=b)).json()["supermarket"] == "lidl"

    plan = (await client.post("/v1/plans/generate", headers=a, json={"week_start": WEEK, "slots": three_meals(1), "use_ai": False})).json()
    seen_by_b = (await client.get("/v1/plans", headers=b)).json()
    assert [p["id"] for p in seen_by_b] == [plan["id"]]


async def test_invalid_invite_code(client, user):
    r = await client.post("/v1/household/join", headers=user["headers"], json={"code": "NOPE-NOPE"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "invite_invalid"


async def test_allergies_of_all_members_apply(client):
    a, b = await family(client, "allergy")
    await client.patch("/v1/me", headers=a, json={"allergens": ["sesam"]})
    slots = [{"date": "2026-11-02", "meal": "abend", "eat_at": "19:00"}]
    r = await client.post("/v1/plans/generate", headers=b, json={"week_start": WEEK, "slots": slots, "seed": 3, "use_ai": False})
    assert r.json()["entries"][0]["recipe_title"].startswith("Rote-Linsen")   # Süßkartoffel-Tahin enthält Sesam


async def test_portions_follow_each_members_goal(client):
    a, b = await family(client, "portions")
    await client.patch("/v1/me", headers=a, json={"fitness_goal": "aufbauen", "sex": "maennlich", "birth_year": YEAR - 30,
                                                  "height_cm": 185, "weight_kg": 90, "activity_level": "aktiv"})
    await client.patch("/v1/me", headers=b, json={"fitness_goal": "halten", "sex": "weiblich", "birth_year": YEAR - 30,
                                                  "height_cm": 165, "weight_kg": 58, "activity_level": "sitzend"})
    plan_a = (await client.post("/v1/plans/generate", headers=a, json={"week_start": WEEK, "slots": three_meals(), "use_ai": False})).json()
    plan_b = (await client.get(f"/v1/plans/{WEEK}", headers=b)).json()
    for ea, eb in zip(plan_a["entries"], plan_b["entries"]):
        if ea["recipe_id"]:
            assert ea["my_portion"] > eb["my_portion"]
            assert ea["total_portions"] == ea["my_portion"] + eb["my_portion"]
            assert 0.5 <= eb["my_portion"] <= 2.0 and (ea["my_portion"] * 4).is_integer()

    # Tausch per PUT rechnet die Portionen neu, statt sie vom Client zu übernehmen
    entries = [{k: e[k] for k in ("id", "date", "meal", "eat_at", "recipe_id")} for e in plan_a["entries"]]
    put = await client.put(f"/v1/plans/{WEEK}", headers=b, json={"client_updated_at": dt.datetime.now(dt.UTC).isoformat(), "entries": entries})
    assert [e["my_portion"] for e in put.json()["entries"]] == [e["my_portion"] for e in plan_b["entries"]]


async def test_leave_starts_own_household_and_keeps_plans_with_family(client):
    a, b = await family(client, "leave")
    await client.post("/v1/plans/generate", headers=a, json={"week_start": WEEK, "slots": three_meals(1), "use_ai": False})
    r = await client.post("/v1/household/leave", headers=b)
    assert [m["is_me"] for m in r.json()["members"]] == [True]
    assert (await client.get("/v1/plans", headers=b)).json() == []
    assert (await client.get("/v1/me", headers=b)).json()["supermarket"] == "lidl"   # Einstellungen als Startwert übernommen
    assert len((await client.get("/v1/plans", headers=a)).json()) == 1
    assert (await client.get("/v1/household", headers=a)).json()["household_size"] == 1


async def test_deleting_member_keeps_household_for_others(client):
    a, b = await family(client, "delete")
    await client.post("/v1/plans/generate", headers=a, json={"week_start": WEEK, "slots": three_meals(1), "use_ai": False})
    assert (await client.delete("/v1/me", headers=b)).status_code == 204
    assert len((await client.get("/v1/plans", headers=a)).json()) == 1
    assert len((await client.get("/v1/household", headers=a)).json()["members"]) == 1
