"""Haushalt: gemeinsame Einschränkungen aller Mitglieder und Portionen je Person."""
from dataclasses import dataclass

from app.models import Household, User
from app.services.fitness import targets_for

PORTION_STEP = 0.25
MIN_PORTION, MAX_PORTION = 0.5, 2.0
# Anteil einer Mahlzeit am Tagesbedarf; wird auf die tatsächlichen Slots des Tages normiert.
MEAL_KCAL_SHARE = {"fruehstueck": 0.25, "mittag": 0.35, "abend": 0.30, "snack": 0.10}


@dataclass(frozen=True)
class Constraints:
    appliances: list[str]
    allergens: list[str]
    diet_tags: list[str]
    dislikes: list[str]
    persons: int


def constraints_for(user: User) -> Constraints:
    """Ein Gericht muss für alle passen: Allergien, Ernährungsformen und Abneigungen aller Mitglieder zählen."""
    h = user.household
    members = h.members or [user]
    return Constraints(
        appliances=list(h.appliances),
        allergens=sorted({a for m in members for a in m.allergens}),
        diet_tags=sorted({d for m in members for d in m.diet_tags}),
        dislikes=sorted({d for m in members for d in m.dislikes}),
        persons=h.household_size,
    )


def slot_kcal_targets(slots, day_kcal: int | None) -> list[float | None]:
    """Verteilt einen Tagesbedarf nach MEAL_KCAL_SHARE auf die Slots (Objekte mit .date/.meal) des jeweiligen Tages."""
    if day_kcal is None:
        return [None] * len(slots)
    share_per_day: dict = {}
    for s in slots:
        share_per_day[s.date] = share_per_day.get(s.date, 0.0) + MEAL_KCAL_SHARE[s.meal]
    return [day_kcal * MEAL_KCAL_SHARE[s.meal] / share_per_day[s.date] for s in slots]


def reference_kcal_targets(slots, household: Household) -> list[float | None]:
    """Mittel der Slot-Ziele aller Mitglieder mit Fitnessziel — Grundlage der Rezeptauswahl."""
    per_member = [slot_kcal_targets(slots, t.kcal) for m in household.members if (t := targets_for(m))]
    if not per_member:
        return [None] * len(slots)
    return [sum(values) / len(values) for values in zip(*per_member)]


def member_portion(recipe_kcal: int | None, slot_target: float | None) -> float:
    if not recipe_kcal or slot_target is None:
        return 1.0
    portion = round(slot_target / recipe_kcal / PORTION_STEP) * PORTION_STEP
    return min(MAX_PORTION, max(MIN_PORTION, portion))


def assign_portions(slots, recipes: list, household: Household) -> list[tuple[dict[str, float], float]]:
    """Je Slot: ({user_id: Portion}, Gesamtportionen inkl. Personen ohne App à 1 Portion)."""
    guests = max(0, household.household_size - len(household.members))
    targets = {str(m.id): slot_kcal_targets(slots, t.kcal if (t := targets_for(m)) else None) for m in household.members}
    result = []
    for i, recipe in enumerate(recipes):
        kcal = recipe.kcal if recipe else None
        portions = {member_id: member_portion(kcal, member_targets[i]) for member_id, member_targets in targets.items()}
        result.append((portions, sum(portions.values()) + guests))
    return result
