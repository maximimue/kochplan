from fastapi import APIRouter

from app.auth.deps import Locale
from app.i18n import labels
from app.vocab import SUPERMARKETS

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/vocab")
async def vocab(locale: Locale):
    """Auswahllisten fürs Onboarding inkl. lokalisierter Labels."""
    return {
        "appliances": labels("appliances", locale),
        "allergens": labels("allergens", locale),
        "diet_tags": labels("diet_tags", locale),
        "meal_types": labels("meal_types", locale),
        "supermarkets": {k: {"label": v, "price_tier": SUPERMARKETS[k]} for k, v in labels("supermarkets", locale).items()},
    }
