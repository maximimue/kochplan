"""Kontrolliertes Vokabular. Keys sind sprachneutral (ASCII), Labels kommen aus i18n."""

APPLIANCES = {
    "herd", "backofen", "mikrowelle", "thermomix", "airfryer",
    "wasserkocher", "mixer", "dampfgarer", "slowcooker", "grill",
}

# 14 EU-Hauptallergene (LMIV) + Laktose als eigene Unverträglichkeit
ALLERGENS = {
    "gluten", "krebstiere", "eier", "fisch", "erdnuesse", "soja", "milch",
    "schalenfruechte", "sellerie", "senf", "sesam", "sulfite", "lupinen",
    "weichtiere", "laktose",
}

DIET_TAGS = {"vegan", "vegetarisch", "pescetarisch"}

MEAL_TYPES = {"fruehstueck", "mittag", "abend", "snack"}

PRICE_TIERS = ("discount", "standard", "bio")

SUPERMARKETS = {
    "aldi": "discount", "lidl": "discount", "netto": "discount", "penny": "discount",
    "rewe": "standard", "edeka": "standard", "kaufland": "standard",
    "denns": "bio", "alnatura": "bio", "bio_company": "bio",
}

# Mengeneinheit im Rezept -> (Basiseinheit der Zutat, Faktor)
UNIT_CONVERSION: dict[str, tuple[str | None, float]] = {
    "g": ("kg", 0.001), "kg": ("kg", 1.0),
    "ml": ("l", 0.001), "l": ("l", 1.0),
    "el": ("l", 0.015), "tl": ("l", 0.005),
    "stk": ("stk", 1.0), "bund": ("stk", 1.0),
    "prise": (None, 0.0),
}


def price_tier(supermarket: str | None) -> str:
    return SUPERMARKETS.get(supermarket or "", "standard")
