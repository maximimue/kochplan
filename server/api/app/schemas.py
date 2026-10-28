import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.services.fitness import MAX_AGE, MIN_AGE, Targets, compute_targets
from app.vocab import (
    ACTIVITY_LEVELS, ALLERGENS, APPLIANCES, DIET_TAGS, FITNESS_GOALS, MEAL_TYPES, PRICE_TIERS, SEXES,
    SUPERMARKETS, UNIT_CONVERSION,
)


def _check(values: list[str], allowed: set[str], field: str) -> list[str]:
    cleaned = sorted({v.strip().lower() for v in values if v.strip()})
    bad = [v for v in cleaned if v not in allowed]
    if bad:
        raise ValueError(f"Unbekannte Werte in {field}: {', '.join(bad)}")
    return cleaned


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- Auth
class AppleLoginIn(BaseModel):
    id_token: str
    raw_nonce: str | None = None          # iOS: Klartext-Nonce, Token enthält sha256(nonce)
    display_name: str | None = None       # Apple liefert den Namen nur beim allerersten Login


class GoogleLoginIn(BaseModel):
    id_token: str


class DevLoginIn(BaseModel):
    email: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: uuid.UUID
    is_new_user: bool = False


# --------------------------------------------------------------------------- Profil
class ProfileOut(ORM):
    id: uuid.UUID
    email: str | None
    display_name: str | None
    locale: str
    timezone: str
    supermarket: str | None
    weekly_budget_cents: int | None
    household_size: int
    appliances: list[str]
    allergens: list[str]
    diet_tags: list[str]
    dislikes: list[str]
    fitness_goal: str | None
    sex: str | None
    birth_year: int | None
    height_cm: int | None
    weight_kg: float | None
    activity_level: str | None
    updated_at: dt.datetime

    # Zielwerte flach statt als verschachteltes Objekt: ein nullable `$ref` kann der
    # swift-openapi-generator im 3.0-Stil nicht sauber als Optional abbilden.
    def _targets(self) -> Targets | None:
        return compute_targets(self.fitness_goal, self.sex, self.birth_year, self.height_cm,
                               self.weight_kg, self.activity_level)

    @computed_field
    @property
    def target_kcal(self) -> int | None:
        return t.kcal if (t := self._targets()) else None

    @computed_field
    @property
    def target_protein_g(self) -> int | None:
        return t.protein_g if (t := self._targets()) else None

    @computed_field
    @property
    def target_fat_g(self) -> int | None:
        return t.fat_g if (t := self._targets()) else None

    @computed_field
    @property
    def target_carbs_g(self) -> int | None:
        return t.carbs_g if (t := self._targets()) else None

    @computed_field
    @property
    def recommended_meals_per_day(self) -> int | None:
        return t.meals_per_day if (t := self._targets()) else None

    # Nullable wie die übrigen Zielwerte (null = keine Ziele): ein Pflicht-Bool würde neue Clients
    # gegen einen noch nicht aktualisierten Server beim Dekodieren scheitern lassen.
    @computed_field
    @property
    def fitness_deficit_capped(self) -> bool | None:
        return t.deficit_capped if (t := self._targets()) else None


class ProfilePatch(BaseModel):
    display_name: str | None = None
    locale: str | None = None
    timezone: str | None = None
    supermarket: str | None = None
    weekly_budget_cents: Annotated[int, Field(ge=0)] | None = None
    household_size: Annotated[int, Field(ge=1, le=12)] | None = None
    appliances: list[str] | None = None
    allergens: list[str] | None = None
    diet_tags: list[str] | None = None
    dislikes: list[str] | None = None
    # "" = kein Fitnessziel: der generierte Swift-Client lässt nil-Felder weg und kann kein explizites null senden.
    fitness_goal: str | None = None
    sex: str | None = None
    birth_year: int | None = None
    height_cm: Annotated[int, Field(ge=120, le=230)] | None = None
    weight_kg: Annotated[float, Field(ge=35, le=300)] | None = None
    activity_level: str | None = None

    @field_validator("fitness_goal")
    @classmethod
    def _goal(cls, v):
        if not v:
            return None
        if v not in FITNESS_GOALS:
            raise ValueError(f"Unbekanntes Fitnessziel: {v}")
        return v

    @field_validator("sex")
    @classmethod
    def _sex(cls, v):
        if v is not None and v not in SEXES:
            raise ValueError(f"Unbekannte Angabe: {v}")
        return v

    @field_validator("activity_level")
    @classmethod
    def _activity(cls, v):
        if v is not None and v not in ACTIVITY_LEVELS:
            raise ValueError(f"Unbekanntes Aktivitätslevel: {v}")
        return v

    @field_validator("birth_year")
    @classmethod
    def _birth_year(cls, v):
        if v is not None and not MIN_AGE <= dt.date.today().year - v <= MAX_AGE:
            raise ValueError(f"Alter muss zwischen {MIN_AGE} und {MAX_AGE} Jahren liegen")
        return v

    @field_validator("supermarket")
    @classmethod
    def _sm(cls, v):
        if v is not None and v not in SUPERMARKETS:
            raise ValueError(f"Unbekannter Supermarkt: {v}")
        return v

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        if v is not None:
            from zoneinfo import ZoneInfo
            ZoneInfo(v)
        return v

    _ap = field_validator("appliances")(lambda cls, v: None if v is None else _check(v, APPLIANCES, "appliances"))
    _al = field_validator("allergens")(lambda cls, v: None if v is None else _check(v, ALLERGENS, "allergens"))
    _dt = field_validator("diet_tags")(lambda cls, v: None if v is None else _check(v, DIET_TAGS, "diet_tags"))
    _dl = field_validator("dislikes")(lambda cls, v: None if v is None else sorted({x.strip().lower() for x in v if x.strip()}))


# --------------------------------------------------------------------------- Haushalt
class HouseholdMemberOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    email: str | None
    is_me: bool
    has_fitness_goal: bool


class HouseholdOut(BaseModel):
    id: uuid.UUID
    household_size: int
    members: list[HouseholdMemberOut]
    invite_code: str | None
    invite_expires_at: dt.datetime | None


class JoinHouseholdIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


# --------------------------------------------------------------------------- Rezepte
class ThermomixSettings(BaseModel):
    time_s: int = Field(ge=0)
    temp_c: int | None = Field(default=None, ge=0, le=160)
    speed: str            # "1".."10", "Löffel", "Turbo", "Linkslauf 1" ...


class StepIn(BaseModel):
    text: str
    minutes: int | None = Field(default=None, ge=0)
    appliance: str | None = None
    thermomix: ThermomixSettings | None = None


class RecipeIngredientIn(BaseModel):
    name: str
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    note: str | None = None

    @field_validator("unit")
    @classmethod
    def _unit(cls, v):
        if v is not None and v.lower() not in UNIT_CONVERSION:
            raise ValueError(f"Unbekannte Einheit: {v} (erlaubt: {', '.join(UNIT_CONVERSION)})")
        return v.lower() if v else v


class RecipeIn(BaseModel):
    """Import-/Austauschformat für feste Rezepte UND Zielschema für KI-Rezepte."""

    slug: str | None = None
    title: str = Field(min_length=3, max_length=200)
    summary: str | None = None
    servings: int = Field(default=2, ge=1, le=12)
    prep_minutes: int = Field(default=0, ge=0)
    cook_minutes: int = Field(default=0, ge=0)
    passive_minutes: int = Field(default=0, ge=0)
    kcal: int | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    appliances: list[str] = []
    allergens: list[str] = []
    tags: list[str] = []
    meal_types: list[str] = []
    ingredients: list[RecipeIngredientIn] = Field(min_length=1)
    steps: list[StepIn] = Field(min_length=1)
    cost_cents_per_serving: dict[str, int] | None = None   # optional, sonst aus Zutaten berechnet

    _ap = field_validator("appliances")(lambda cls, v: _check(v, APPLIANCES, "appliances"))
    _al = field_validator("allergens")(lambda cls, v: _check(v, ALLERGENS, "allergens"))
    _mt = field_validator("meal_types")(lambda cls, v: _check(v, MEAL_TYPES, "meal_types"))
    _tg = field_validator("tags")(lambda cls, v: sorted({x.strip().lower() for x in v if x.strip()}))

    @field_validator("cost_cents_per_serving")
    @classmethod
    def _cost(cls, v):
        if v is not None and not set(v) <= set(PRICE_TIERS):
            raise ValueError(f"Preis-Tiers müssen aus {PRICE_TIERS} sein")
        return v


class IngredientIn(BaseModel):
    name: str
    base_unit: str = Field(pattern="^(kg|l|stk)$")
    prices: dict[str, int] = {}     # Cent je Basiseinheit und Tier
    allergens: list[str] = []

    _al = field_validator("allergens")(lambda cls, v: _check(v, ALLERGENS, "allergens"))


class RecipeIngredientOut(ORM):
    name: str
    quantity: float | None
    unit: str | None
    note: str | None


class RecipeOut(ORM):
    id: uuid.UUID
    slug: str
    title: str
    summary: str | None
    servings: int
    prep_minutes: int
    cook_minutes: int
    passive_minutes: int
    total_minutes: int
    kcal: int | None
    protein_g: float | None
    fat_g: float | None
    carbs_g: float | None
    cost_cents_per_serving: dict[str, int]
    appliances: list[str]
    allergens: list[str]
    tags: list[str]
    meal_types: list[str]
    steps: list[dict]
    source: str
    ingredients: list[RecipeIngredientOut]
    updated_at: dt.datetime


class RecipeSyncOut(BaseModel):
    server_time: dt.datetime
    recipes: list[RecipeOut]
    deleted_ids: list[uuid.UUID]


class AiRecipeRequest(BaseModel):
    meal: str = "abend"
    wish: str | None = Field(default=None, max_length=300)   # z. B. "etwas mit Kürbis"

    _m = field_validator("meal")(lambda cls, v: _check([v], MEAL_TYPES, "meal")[0])


# --------------------------------------------------------------------------- Pläne
class SlotIn(BaseModel):
    date: dt.date
    meal: str = "abend"
    eat_at: dt.time | None = None

    _m = field_validator("meal")(lambda cls, v: _check([v], MEAL_TYPES, "meal")[0])


class GeneratePlanIn(BaseModel):
    week_start: dt.date
    # 7 Tage × max. 5 Mahlzeiten/Tag (Frühstück/Snack/Mittag/Snack/Abend), siehe iOS-Mahlzeiten-Editor.
    slots: list[SlotIn] = Field(min_length=1, max_length=35)
    use_ai: bool = True
    seed: int | None = None


class PlanEntryIn(BaseModel):
    """Portionen berechnet der Server aus den Fitnesszielen der Mitglieder (kein Client-Feld)."""

    id: uuid.UUID | None = None
    date: dt.date
    meal: str
    eat_at: dt.time | None = None
    recipe_id: uuid.UUID | None = None

    _m = field_validator("meal")(lambda cls, v: _check([v], MEAL_TYPES, "meal")[0])


class PlanPutIn(BaseModel):
    client_updated_at: dt.datetime
    entries: list[PlanEntryIn]


class PlanEntryOut(BaseModel):
    id: uuid.UUID
    date: dt.date
    meal: str
    eat_at: dt.time | None
    total_portions: float   # alle Personen des Haushalts -> Einkauf, Kosten
    my_portion: float       # Portion des anfragenden Mitglieds -> eigene Makros
    recipe_id: uuid.UUID | None
    recipe_title: str | None
    total_minutes: int | None
    start_at: dt.datetime | None
    cost_cents: int | None


class PlanOut(BaseModel):
    id: uuid.UUID
    week_start: dt.date
    entries: list[PlanEntryOut]
    total_cost_cents: int
    budget_cents: int | None
    over_budget: bool
    warnings: list[dict] = []
    updated_at: dt.datetime
    client_updated_at: dt.datetime
    deleted: bool = False
