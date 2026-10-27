import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, Time, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

Tags = ARRAY(String(40))
EMPTY_ARRAY = text("'{}'")


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def tags_col() -> Mapped[list[str]]:
    return mapped_column(Tags, default=list, server_default=EMPTY_ARRAY, nullable=False)


class Timestamps:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- User / Auth
class User(Timestamps, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(10), default="de", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin", nullable=False)
    supermarket: Mapped[str | None] = mapped_column(String(30))
    weekly_budget_cents: Mapped[int | None] = mapped_column(Integer)
    household_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    appliances: Mapped[list[str]] = tags_col()
    allergens: Mapped[list[str]] = tags_col()
    diet_tags: Mapped[list[str]] = tags_col()
    dislikes: Mapped[list[str]] = tags_col()   # Zutaten-Stichworte, z. B. "koriander"

    identities: Mapped[list["AuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))   # apple | google | dev
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="identities")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Timestamps, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    plan: Mapped[str] = mapped_column(String(20), default="mvp")        # mvp | basis | plus
    status: Mapped[str] = mapped_column(String(20), default="active")   # active | past_due | canceled
    source: Mapped[str] = mapped_column(String(20), default="manual")   # manual | storekit | stripe
    ai_requests_per_month: Mapped[int | None] = mapped_column(Integer)  # None = unbegrenzt
    current_period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="subscription")


class AiUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    kind: Mapped[str] = mapped_column(String(40))          # recipe_generate
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------- Rezepte
class Ingredient(Timestamps, Base):
    __tablename__ = "ingredients"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), unique=True)   # normalisiert, lowercase
    base_unit: Mapped[str] = mapped_column(String(10))            # kg | l | stk
    prices: Mapped[dict] = mapped_column(JSONB, default=dict)     # {"discount": cents, ...} je Basiseinheit
    allergens: Mapped[list[str]] = tags_col()


class Recipe(Timestamps, Base):
    __tablename__ = "recipes"
    __table_args__ = (
        Index("ix_recipes_allergens", "allergens", postgresql_using="gin"),
        Index("ix_recipes_appliances", "appliances", postgresql_using="gin"),
        Index("ix_recipes_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    servings: Mapped[int] = mapped_column(Integer, default=2)
    prep_minutes: Mapped[int] = mapped_column(Integer, default=0)     # aktiv
    cook_minutes: Mapped[int] = mapped_column(Integer, default=0)     # aktiv am Gerät
    passive_minutes: Mapped[int] = mapped_column(Integer, default=0)  # Backen, Ruhen, Garen ohne Aufsicht
    kcal: Mapped[int | None] = mapped_column(Integer)                 # je Portion
    protein_g: Mapped[float | None] = mapped_column(Numeric(6, 1))
    fat_g: Mapped[float | None] = mapped_column(Numeric(6, 1))
    carbs_g: Mapped[float | None] = mapped_column(Numeric(6, 1))
    cost_cents_per_serving: Mapped[dict] = mapped_column(JSONB, default=dict)  # je Preis-Tier
    appliances: Mapped[list[str]] = tags_col()
    allergens: Mapped[list[str]] = tags_col()
    tags: Mapped[list[str]] = tags_col()
    meal_types: Mapped[list[str]] = tags_col()   # leer = passt zu jeder Mahlzeit
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(String(10), default="curated")   # curated | ai
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan",
        order_by="RecipeIngredient.position", lazy="selectin",
    )

    @property
    def total_minutes(self) -> int:
        return self.prep_minutes + self.cook_minutes + self.passive_minutes


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[uuid.UUID] = uuid_pk()
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingredients.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")


# --------------------------------------------------------------------------- Planung
class MealPlan(Timestamps, Base):
    __tablename__ = "meal_plans"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[dt.date] = mapped_column(Date)
    # Offline-Sync: Zeitstempel der letzten Änderung auf dem Client (Last-Write-Wins)
    client_updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    entries: Mapped[list["PlanEntry"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan",
        order_by="(PlanEntry.date, PlanEntry.eat_at)", lazy="selectin",
    )


class PlanEntry(Base):
    """Ein Kochtermin: Tag + Mahlzeit + gewünschte Essenszeit -> berechnete Startzeit."""

    __tablename__ = "plan_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(20))
    eat_at: Mapped[dt.time | None] = mapped_column(Time)
    servings: Mapped[int] = mapped_column(Integer, default=1)
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"))
    start_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))  # UTC

    plan: Mapped[MealPlan] = relationship(back_populates="entries")
    recipe: Mapped[Recipe | None] = relationship(lazy="selectin")
