"""Fitness-Ziele: Tagesbedarf nach Mifflin-St Jeor und Makro-Ziele aus dem Profil.
Grobe Schätzung für gesunde Erwachsene, keine medizinische Beratung."""
import datetime as dt
from dataclasses import dataclass

from app.vocab import ACTIVITY_LEVELS

GOAL_KCAL_DELTA = {"abnehmen": -500, "halten": 0, "aufbauen": 300}
PROTEIN_G_PER_KG = {"abnehmen": 2.0, "halten": 1.6, "aufbauen": 2.0}
FAT_SHARE = 0.28
# Ein Defizit drückt nie unter diese Untergrenze (bzw. unter den Gesamtumsatz, falls der schon darunter liegt).
KCAL_FLOOR = {"weiblich": 1200, "maennlich": 1500, "divers": 1350}
MIN_BMI_FOR_DEFICIT = 18.5
MIN_AGE, MAX_AGE = 18, 100


@dataclass(frozen=True)
class Targets:
    kcal: int
    protein_g: int
    fat_g: int
    carbs_g: int
    meals_per_day: int
    deficit_capped: bool   # Defizit wegen Untergewicht/Untergrenze reduziert


def meals_per_day(kcal: int) -> int:
    # ponytail: Schwellen passen zum aktuellen Rezeptbestand (Frühstück ~360, Hauptgericht ~450,
    # Snack ~250 kcal je Portion). Mit größeren/proteinreicheren Rezepten neu kalibrieren.
    if kcal <= 1600:
        return 3
    if kcal <= 2000:
        return 4
    return 5


def compute_targets(
    goal: str | None, sex: str | None, birth_year: int | None, height_cm: int | None,
    weight_kg: float | None, activity_level: str | None, today: dt.date | None = None,
) -> Targets | None:
    if None in (goal, sex, birth_year, height_cm, weight_kg, activity_level):
        return None
    weight = float(weight_kg)
    age = (today or dt.date.today()).year - birth_year
    sex_offset = {"maennlich": 5, "weiblich": -161}.get(sex, -78)
    bmr = 10 * weight + 6.25 * height_cm - 5 * age + sex_offset
    tdee = bmr * ACTIVITY_LEVELS[activity_level]

    kcal = tdee + GOAL_KCAL_DELTA[goal]
    capped = False
    if goal == "abnehmen":
        bmi = weight / (height_cm / 100) ** 2
        floor = tdee if bmi < MIN_BMI_FOR_DEFICIT else min(tdee, KCAL_FLOOR[sex])
        if kcal < floor:
            kcal, capped = floor, True

    kcal = int(round(kcal / 10) * 10)
    protein = round(weight * PROTEIN_G_PER_KG[goal])
    fat = round(kcal * FAT_SHARE / 9)
    carbs = max(0, round((kcal - protein * 4 - fat * 9) / 4))
    return Targets(kcal, protein, fat, carbs, meals_per_day(kcal), capped)


def targets_for(user) -> Targets | None:
    return compute_targets(user.fitness_goal, user.sex, user.birth_year, user.height_cm,
                           user.weight_kg, user.activity_level)
