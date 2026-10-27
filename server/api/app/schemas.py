import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.vocab import ALLERGENS, APPLIANCES, DIET_TAGS, MEAL_TYPES, PRICE_TIERS, SUPERMARKETS, UNIT_CONVERSION


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
    updated_at: dt.datetime


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
    servings: int | None = Field(default=None, ge=1, le=12)

    _m = field_validator("meal")(lambda cls, v: _check([v], MEAL_TYPES, "meal")[0])


class GeneratePlanIn(BaseModel):
    week_start: dt.date
    slots: list[SlotIn] = Field(min_length=1, max_length=28)
    use_ai: bool = True
    seed: int | None = None


class PlanEntryIn(BaseModel):
    id: uuid.UUID | None = None
    date: dt.date
    meal: str
    eat_at: dt.time | None = None
    servings: int = Field(default=1, ge=1, le=12)
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
    servings: int
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
