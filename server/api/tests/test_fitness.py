import datetime as dt
import random
import uuid

import pytest

from app.models import Recipe
from app.schemas import SlotIn
from app.services.fitness import compute_targets, meals_per_day
from app.services.household import slot_kcal_targets
from app.services.planner import fitness_score, pick

TODAY = dt.date(2026, 10, 28)
BODY = {"sex": "maennlich", "birth_year": 1996, "height_cm": 180, "weight_kg": 80, "activity_level": "maessig"}
DAY = dt.date(2026, 11, 2)


def targets(goal, **override):
    return compute_targets(goal, **{**BODY, **override}, today=TODAY)


def test_maintenance_targets_mifflin_st_jeor():
    t = targets("halten")
    # Grundumsatz = 10·80 + 6,25·180 − 5·30 + 5 = 1780; × 1,55 = 2759 → 2760
    assert t.kcal == 2760
    assert t.protein_g == 128
    assert t.fat_g == 86
    assert t.protein_g * 4 + t.fat_g * 9 + t.carbs_g * 4 == pytest.approx(t.kcal, abs=4)
    assert t.meals_per_day == 5 and not t.deficit_capped


def test_goal_shifts_kcal():
    assert targets("abnehmen").kcal == 2260
    assert targets("aufbauen").kcal == 3060


def test_no_deficit_when_underweight():
    t = targets("abnehmen", weight_kg=55)   # BMI ≈ 17
    assert t.deficit_capped
    assert t.kcal == targets("halten", weight_kg=55).kcal


def test_deficit_never_below_floor():
    t = targets("abnehmen", sex="weiblich", birth_year=1950, height_cm=155, weight_kg=60, activity_level="sitzend")
    assert t.kcal == 1200 and t.deficit_capped


def test_incomplete_profile_has_no_targets():
    assert compute_targets("halten", None, 1996, 180, 80, "maessig") is None
    assert compute_targets(None, **BODY) is None


def test_meals_per_day_scales_with_kcal():
    assert [meals_per_day(k) for k in (1500, 1800, 2500)] == [3, 4, 5]


def test_slot_targets_split_day_by_meal_share():
    slots = [SlotIn(date=DAY, meal=m) for m in ("fruehstueck", "mittag", "abend")]
    shares = slot_kcal_targets(slots, 1800)
    assert sum(shares) == pytest.approx(1800)
    assert shares == pytest.approx([500, 700, 600])
    assert slot_kcal_targets(slots, None) == [None, None, None]


def test_pick_prefers_recipes_near_kcal_target():
    pool = [Recipe(id=uuid.uuid4(), title=f"r{k}", kcal=k, protein_g=10, meal_types=["abend"],
                   cost_cents_per_serving={}) for k in range(200, 1200, 100)]
    slot = SlotIn(date=DAY, meal="abend")
    for seed in range(20):
        r = pick(pool, slot, 1, "standard", None, 1, random.Random(seed), kcal_target=600)
        assert abs(r.kcal - 600) <= 200


def test_fitness_score_rewards_protein():
    assert fitness_score(Recipe(kcal=500, protein_g=40), 500) < fitness_score(Recipe(kcal=500, protein_g=5), 500)


async def test_profile_fitness_targets_roundtrip(client, user):
    body = {**BODY, "fitness_goal": "aufbauen", "birth_year": dt.date.today().year - 30}
    r = await client.patch("/v1/me", headers=user["headers"], json=body)
    assert r.status_code == 200, r.text
    assert r.json()["target_kcal"] == 3060
    assert r.json()["recommended_meals_per_day"] == 5

    # "" = kein Ziel mehr; Körperdaten bleiben erhalten
    r = await client.patch("/v1/me", headers=user["headers"], json={"fitness_goal": ""})
    assert r.json()["fitness_goal"] is None and r.json()["target_kcal"] is None
    assert r.json()["weight_kg"] == 80


async def test_profile_rejects_minor_with_error_envelope(client, user):
    r = await client.patch("/v1/me", headers=user["headers"], json={"birth_year": dt.date.today().year - 15})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"
    assert "birth_year" in r.json()["error"]["message"]


async def test_fitness_plan_warns_when_targets_unreachable(client, user):
    body = {**BODY, "fitness_goal": "aufbauen", "birth_year": dt.date.today().year - 30,
            "appliances": ["herd", "backofen"], "supermarket": "lidl"}
    await client.patch("/v1/me", headers=user["headers"], json=body)
    slots = [{"date": f"2026-11-0{2 + i}", "meal": "abend", "eat_at": "19:00"} for i in range(2)]
    r = await client.post("/v1/plans/generate", headers=user["headers"],
                          json={"week_start": "2026-11-02", "slots": slots, "use_ai": False})
    codes = {w["code"] for w in r.json()["warnings"]}
    assert {"kcal_target_missed", "protein_target_missed"} <= codes
