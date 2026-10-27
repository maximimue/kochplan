"""KI-Rezeptgenerierung. Läuft ausschließlich serverseitig (API-Key, Kosten, Limits).
Jede Anfrage wird in ai_usage protokolliert — auch im MVP und auch bei Fehlern."""
import datetime as dt
import json
import re

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.errors import AppError
from app.models import AiUsage, Recipe, Subscription, User
from app.schemas import RecipeIn
from app.services.recipes import load_catalog, upsert_recipe
from app.vocab import ALLERGENS, APPLIANCES, MEAL_TYPES, UNIT_CONVERSION

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = f"""Du bist Rezeptentwickler für eine deutsche Kochplan-App.
Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, ohne Markdown, ohne Erklärtext.
Schema (Felder):
- title, summary (1 Satz), servings (int)
- prep_minutes, cook_minutes, passive_minutes (int; realistisch, passive = Backen/Ruhen ohne Aufsicht)
- kcal (je Portion, int), protein_g, fat_g, carbs_g (je Portion)
- appliances: Liste aus {sorted(APPLIANCES)} — nur Geräte, die wirklich benötigt werden
- allergens: Liste aus {sorted(ALLERGENS)} — vollständig und ehrlich angeben
- tags: freie Stichworte (z. B. "vegetarisch", "schnell", "meal-prep")
- meal_types: Liste aus {sorted(MEAL_TYPES)}
- ingredients: Liste von {{"name", "quantity", "unit", "note"}}; unit aus {sorted(UNIT_CONVERSION)}; Zutatennamen auf Deutsch, Singular, ohne Markennamen
- steps: Liste von {{"text", "minutes", "appliance", "thermomix"}}; thermomix nur wenn Thermomix verfügbar: {{"time_s", "temp_c", "speed"}}
- cost_cents_per_serving: {{"discount": int, "standard": int, "bio": int}} grobe Schätzung deutscher Supermarktpreise
Zutaten müssen in deutschen Supermärkten erhältlich sein."""


def _month_start() -> dt.datetime:
    now = dt.datetime.now(dt.UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class AiService:
    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.s = settings or get_settings()
        self.transport = transport

    @property
    def available(self) -> bool:
        return self.s.ai_enabled

    async def check_limits(self, session: AsyncSession, user: User) -> None:
        minute_ago = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)
        recent = await session.scalar(
            select(func.count()).select_from(AiUsage)
            .where(AiUsage.user_id == user.id, AiUsage.created_at >= minute_ago)
        )
        if recent >= self.s.ai_rate_per_minute:
            raise AppError("ai_rate_limited", 429)
        if not self.s.ai_limits_enabled:
            return
        sub = await session.get(Subscription, user.id)
        if sub is None or sub.status != "active":
            raise AppError("ai_monthly_limit", 402)
        if sub.ai_requests_per_month is None:
            return
        used = await session.scalar(
            select(func.count()).select_from(AiUsage)
            .where(AiUsage.user_id == user.id, AiUsage.success.is_(True), AiUsage.created_at >= _month_start())
        )
        if used >= sub.ai_requests_per_month:
            raise AppError("ai_monthly_limit", 402)

    def _user_prompt(self, user: User, meal: str, wish: str | None, avoid_titles: list[str]) -> str:
        lines = [
            f"Mahlzeit: {meal}",
            f"Portionen: {user.household_size}",
            f"Verfügbare Geräte (nur diese verwenden): {', '.join(user.appliances) or 'keine Angabe'}",
            f"Strikt ausschließen (Allergene): {', '.join(user.allergens) or 'keine'}",
            f"Ernährungsform: {', '.join(user.diet_tags) or 'keine Einschränkung'}",
            f"Nicht mögen: {', '.join(user.dislikes) or '-'}",
        ]
        if user.weekly_budget_cents:
            lines.append(f"Wochenbudget gesamt: {user.weekly_budget_cents / 100:.2f} € — eher günstig kochen")
        if wish:
            lines.append(f"Wunsch: {wish}")
        if avoid_titles:
            lines.append(f"Nicht wiederholen: {'; '.join(avoid_titles[:30])}")
        return "\n".join(lines)

    async def _call(self, prompt: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient(timeout=self.s.anthropic_timeout_s, transport=self.transport) as client:
            r = await client.post(API_URL, headers={
                "x-api-key": self.s.anthropic_api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }, json={
                "model": self.s.anthropic_model,
                "max_tokens": 4000,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            })
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    def _cost(self, tin: int, tout: int) -> int:
        return round(tin * self.s.ai_price_input_per_mtok_usd + tout * self.s.ai_price_output_per_mtok_usd)

    async def generate_recipe(
        self, session: AsyncSession, user: User, meal: str = "abend",
        wish: str | None = None, avoid_titles: list[str] | None = None,
    ) -> Recipe:
        if not self.available:
            raise AppError("ai_unavailable", 503)
        await self.check_limits(session, user)

        usage = AiUsage(user_id=user.id, kind="recipe_generate", model=self.s.anthropic_model)
        session.add(usage)
        try:
            text, tin, tout = await self._call(self._user_prompt(user, meal, wish, avoid_titles or []))
            usage.input_tokens, usage.output_tokens, usage.cost_micro_usd = tin, tout, self._cost(tin, tout)
            data = RecipeIn.model_validate(json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()))
            if not data.meal_types:
                data.meal_types = [meal]

            # Serverseitig gegenprüfen — der KI wird nicht blind vertraut.
            catalog = await load_catalog(session)
            derived = {a for i in data.ingredients if (c := catalog.get(i.name.strip().lower())) for a in c.allergens}
            if (set(data.allergens) | derived) & set(user.allergens):
                raise AppError("ai_constraint_violation", 422, detail="allergens")
            if not set(data.appliances) <= set(user.appliances):
                raise AppError("ai_constraint_violation", 422, detail="appliances")
            disliked = [d for d in user.dislikes if any(d in i.name.lower() for i in data.ingredients)]
            if disliked:
                raise AppError("ai_constraint_violation", 422, detail="dislikes")

            recipe, _ = await upsert_recipe(session, data, source="ai", owner_user_id=user.id, catalog=catalog)
            usage.success = True
            await session.commit()
            return recipe
        except AppError as e:
            usage.success, usage.error = False, e.code
            await session.commit()
            raise
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
            usage.success, usage.error = False, f"{type(e).__name__}: {str(e)[:500]}"
            await session.commit()
            raise AppError("ai_invalid_output" if not isinstance(e, httpx.HTTPError) else "ai_unavailable",
                           502 if not isinstance(e, httpx.HTTPError) else 503)


_service: AiService | None = None


def get_ai_service() -> AiService:
    global _service
    if _service is None:
        _service = AiService()
    return _service
