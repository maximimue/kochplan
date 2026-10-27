#!/usr/bin/env python3
"""Übersetzt rezepte_200.json (freies Generator-Format) ins RecipeIn-Importschema
des Projekts und erweitert den Zutatenkatalog (seed/ingredients.json)."""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAW = Path(sys.argv[1])
EXISTING_INGREDIENTS = Path(sys.argv[2])
OUT_RECIPES = Path(sys.argv[3])
OUT_INGREDIENTS = Path(sys.argv[4])

UNIT_MAP = {
    "g": "g", "ml": "ml", "EL": "el", "TL": "tl", "Prise": "prise",
    "Stück": "stk", "Zehe": "stk", "Zehen": "stk", "Stange": "stk",
    "Knolle": "stk", "Knollen": "stk",
}
UNIT_BUCKET = {  # welcher Preis-Basis (kg|l|stk) eine Rezept-Einheit zuarbeitet
    "g": "kg", "ml": "l", "el": "l", "tl": "l", "stk": "stk", "prise": None,
}

APPLIANCE_MAP = {"Herd": "herd", "Backofen": "backofen", "Mixer/Pürierstab": "mixer"}

ALLERGEN_MAP = {
    "Milcheiweiß": "milch", "Nüsse": "schalenfruechte", "Sesam": "sesam",
    "Ei": "eier", "Erdnuss": "erdnuesse", "Sellerie": "sellerie", "Senf": "senf",
}

KATEGORIE_MEAL = {
    "Frühstück": ["fruehstueck"], "Snack": ["snack"], "Dessert": ["snack"],
    "Pfannengericht": ["mittag", "abend"], "Auflauf": ["mittag", "abend"],
    "Salat": ["mittag", "abend"], "Suppe": ["mittag", "abend"],
    "Bowl": ["mittag", "abend"], "Curry": ["mittag", "abend"], "Pasta": ["mittag", "abend"],
}

# Namens-Aliase, um Dubletten mit dem bestehenden Katalog zu vermeiden (gleiche Zutat, andere Schreibweise)
NAME_ALIAS = {"Tahini": "Tahin", "Risotto-Reis": "Risottoreis"}

# Zutat+Einheit, die (wie "Currypulver"/g im bestehenden Katalog) in Gramm umgerechnet werden,
# damit sie zum bestehenden kg-Katalogeintrag passen, statt einen neuen l-Eintrag zu erzeugen.
# ponytail: grobe Dichte-Schätzung, kein Anspruch auf Präzision (passt zum Rest der Kostenschätzung)
GRAM_CONVERT = {
    ("zwiebel", "stk"): 120.0,   # 1 Stück ~120g
    ("currypulver", "el"): 6.0,  # 1 EL Pulver ~6g
    ("chiasamen", "el"): 12.0,   # 1 EL ~12g
    ("tahin", "el"): 15.0,       # 1 EL Paste ~15g
    ("karotte", "stk"): 80.0,    # 1 Stück ~80g (sonst widerspricht es den 4 Rezepten mit Gramm-Angabe)
}

NUT_ALLERGEN_TREE = {
    "cashewkerne", "walnüsse", "haselnüsse", "mandeln", "mandelmehl", "mandelmus", "pekannüsse", "pinienkerne",
}
NUT_ALLERGEN_PEANUT = {"erdnüsse", "erdnussmus"}
NUT_ALLERGEN_SESAM = {"sesam", "sesamöl", "tahin"}
DAIRY_PROTEIN = {
    "feta laktosefrei", "frischkäse laktosefrei", "laktosefreier frischkäse", "laktosefreier gorgonzola",
    "laktosefreier hartkäse", "laktosefreier joghurt", "laktosefreier mozzarella", "laktosefreier parmesan",
    "laktosefreier ricotta", "laktosefreier schmelzkäse", "laktosefreie sahne", "laktosefreie milch",
    "butter laktosefrei",
}
SELLERIE_SET = {"sellerie", "knollensellerie"}
SENF_SET = {"senf"}

CATEGORY_DEFAULT = {  # zutat_kategorie -> {basis: (discount, standard, bio)} Cent
    "Gemüse": {"kg": (199, 249, 399), "stk": (40, 55, 90)},
    "Gewürz/Kräuter": {"kg": (1500, 2000, 3000), "l": (1500, 2000, 3000), "stk": (40, 60, 90)},
    "Fett/Öl": {"l": (900, 1100, 1500), "kg": (900, 1100, 1500)},
    "Getreide/Stärke": {"kg": (250, 330, 499), "stk": (150, 200, 300)},
    "Flüssigkeit": {"l": (80, 150, 250)},
    "Hülsenfrucht/Protein": {"kg": (300, 380, 550), "stk": (25, 30, 45)},
    "Milchprodukt (laktosefrei)": {"kg": (1200, 1600, 2200), "l": (250, 330, 450)},
    "Säure/Topping": {"l": (300, 400, 600), "kg": (300, 400, 600)},
    "Nuss/Kern": {"kg": (1200, 1600, 2200)},
    "Süße": {"kg": (600, 900, 1300), "l": (600, 900, 1300)},
}

# Manuelle Preis-Überschreibungen für Zutaten, die ich besser als den Kategorie-Default einschätzen kann.
# (discount, standard, bio) in Cent je Basiseinheit (kg|l|stk)
MANUAL_PRICE = {
    "ananas": (300, 380, 550), "apfel": (30, 40, 60), "aubergine": (90, 120, 180),
    "avocado": (90, 120, 180), "banane": (20, 25, 40), "birne": (35, 45, 70),
    "blumenkohl": (199, 249, 399), "brokkoli": (249, 299, 449), "champignons": (499, 599, 899),
    "drachenfrucht gefroren": (1200, 1500, 1800), "fenchel": (90, 120, 180),
    "granatapfelkerne": (1800, 2200, 2800), "grünkohl": (399, 499, 699), "gurke": (60, 80, 120),
    "hokkaido-kürbis": (199, 249, 349), "karotte": (129, 169, 269), "karotte geraspelt": (15, 20, 30),
    "kartoffel": (99, 139, 249), "kirschtomaten": (499, 599, 799), "knollensellerie": (199, 249, 399),
    "mais": (299, 349, 499), "maiskolben": (60, 80, 120), "mango": (120, 150, 220),
    "maronen gegart": (1200, 1500, 1900), "oliven": (899, 1099, 1499), "orange": (40, 50, 80),
    "paprika": (60, 80, 120), "pastinake": (299, 349, 499), "pflaumen": (25, 30, 45),
    "pilze": (499, 599, 899), "radicchio": (599, 699, 999), "rettich": (199, 249, 399),
    "rosenkohl": (299, 399, 599), "rote bete": (199, 249, 399), "rote bete gekocht": (299, 399, 599),
    "rotkohl": (149, 199, 349), "rucola": (999, 1199, 1599), "spinat": (399, 499, 699),
    "tomate": (35, 45, 70), "tomaten": (249, 299, 449), "tomaten gehackt": (149, 199, 299),
    "tomatensauce": (199, 249, 349), "wassermelone": (99, 149, 249), "weißkohl": (99, 149, 249),
    "zucchini": (70, 90, 140), "zucchini (als zoodles)": (70, 90, 140),
    "rote zwiebel": (25, 35, 55), "mais-tortillas (glutenfrei)": (250, 330, 450),
    "gefrorene banane": (20, 25, 40), "gefrorene beeren": (599, 699, 999), "gemischte beeren": (599, 699, 999),
    "knoblauch": (10, 12, 20), "ingwer": (15, 20, 30), "kürbispüree": (299, 349, 499),
    "grüner spargel": (699, 899, 1199), "grüne bohnen": (299, 399, 599), "lauch": (150, 200, 300),
    "sellerie": (150, 200, 300),
    # Gewürze/Kräuter
    "basilikum": (10, 15, 25), "dill": (10, 15, 25), "koriander": (10, 15, 25), "minze": (10, 15, 25),
    "petersilie": (10, 15, 25), "rosmarin": (10, 15, 25), "salbei": (10, 15, 25), "schnittlauch": (10, 15, 25),
    "thymian": (10, 15, 25), "zitronengras": (20, 25, 35), "muskatnuss": (3000, 4000, 6000),
    "safran": (25000, 35000, 50000), "sumach": (2500, 3500, 5000), "harissa": (1200, 1500, 2000),
    "garam masala": (1800, 2500, 3500), "kreuzkümmel": (1500, 2000, 3000), "kurkuma": (1500, 2000, 3000),
    "kümmel": (1500, 2000, 3000), "paprikapulver": (1200, 1600, 2500), "chilipulver": (1800, 2500, 3500),
    "chiliflocken": (1800, 2500, 3500), "oregano": (1500, 2000, 3000), "kardamom": (3000, 4000, 6000),
    "vanille": (4000, 6000, 9000), "agar-agar": (3000, 4000, 6000), "backpulver (glutenfrei)": (600, 800, 1200),
    "kakaopulver": (900, 1200, 1800), "senf": (1200, 1600, 2200),
    "currypaste (fischsauce-frei)": (1600, 2000, 2800), "currypaste massaman (fischsauce-frei)": (1600, 2000, 2800),
    "currypaste panang (fischsauce-frei)": (1600, 2000, 2800), "currypaste grün (fischsauce-frei)": (1600, 2000, 2800),
    "currypaste rot (fischsauce-frei)": (1600, 2000, 2800), "currypulver gelb": (1500, 2000, 3000),
    "chilisauce": (600, 800, 1200),
    # Fett/Öl
    "kokosöl": (1200, 1500, 1900), "sesamöl": (1400, 1800, 2400), "öl zum braten": (900, 1100, 1500),
    "butter laktosefrei": (1600, 2000, 2800),
    # Getreide/Stärke
    "buchweizenmehl": (349, 449, 649), "hirse": (349, 449, 649), "kichererbsenmehl": (399, 499, 699),
    "kichererbsennudeln": (599, 699, 999), "linsennudeln": (599, 699, 999), "maisnudeln": (499, 599, 899),
    "milchreis (glutenfrei)": (299, 349, 499), "polenta/maisgrieß": (249, 299, 449), "quinoa": (899, 1099, 1499),
    "reis": (199, 249, 399), "reis (gekocht, kalt)": (199, 249, 399), "reismehl": (399, 499, 699),
    "reisnudeln": (399, 499, 699), "reisnudeln-pasta": (399, 499, 699), "glutenfreie gnocchi": (499, 599, 899),
    "glutenfreie lasagneplatten": (599, 699, 999), "glutenfreies granola": (899, 1199, 1699),
    "glutenfreie haferflocken": (399, 499, 699),
    # Hülsenfrucht/Protein
    "ei": (30, 40, 60), "kichererbsen": (300, 380, 550), "kidneybohnen": (300, 380, 550),
    "schwarze bohnen": (300, 380, 550), "weiße bohnen": (300, 380, 550), "braune linsen": (299, 379, 549),
    "rote linsen": (249, 329, 499), "rote linsen (gemahlen)": (299, 379, 549),
    "jackfruit (jung, aus der dose)": (599, 799, 1099), "leinsamen geschrotet": (599, 799, 1099),
    # Milchprodukt (laktosefrei)
    "feta laktosefrei": (1800, 2200, 2800), "frischkäse laktosefrei": (1400, 1700, 2200),
    "laktosefreier frischkäse": (1400, 1700, 2200), "laktosefreier gorgonzola": (2200, 2800, 3500),
    "laktosefreier hartkäse": (1800, 2200, 2800), "laktosefreier joghurt": (350, 450, 650),
    "laktosefreier mozzarella": (1600, 2000, 2600), "laktosefreier parmesan": (2500, 3000, 3800),
    "laktosefreier ricotta": (1400, 1700, 2200), "laktosefreier schmelzkäse": (1600, 2000, 2600),
    "laktosefreie sahne": (350, 450, 650), "laktosefreie milch": (150, 200, 280), "hafermilch": (150, 200, 280),
    # Süße
    "ahornsirup": (1800, 2200, 2900), "datteln": (799, 999, 1399), "getrocknete cranberries": (1800, 2200, 2900),
    "honig": (1400, 1800, 2600), "kokosraspeln": (899, 1099, 1499),
    # Nuss/Kern
    "cashewkerne": (1600, 2000, 2600), "erdnüsse": (700, 900, 1300), "erdnussmus": (900, 1200, 1700),
    "haselnüsse": (1600, 2000, 2600), "kürbiskerne": (1400, 1800, 2400), "mandelmehl": (1800, 2200, 2900),
    "mandelmus": (1600, 2000, 2700), "mandeln": (1600, 2000, 2700), "pekannüsse": (1800, 2200, 2900),
    "pinienkerne": (2800, 3400, 4200), "sesam": (900, 1200, 1700), "walnüsse": (1400, 1800, 2400),
    # Säure/Topping
    "kapern": (1200, 1600, 2200), "kokosaminos": (1800, 2200, 2900), "limettensaft": (600, 800, 1200),
    "reisessig": (500, 700, 1000), "sojasauce-alternative (kokosaminos)": (1800, 2200, 2900),
    "zitronensaft": (500, 700, 1000),
    # Flüssigkeit
    "gemüsebrühe": (50, 80, 150), "kokosmilch": (330, 450, 600), "wasser": (0, 0, 0),
}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def slugify(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:150]


def allergens_for(norm: str) -> list[str]:
    out = []
    if norm in NUT_ALLERGEN_TREE:
        out.append("schalenfruechte")
    if norm in NUT_ALLERGEN_PEANUT:
        out.append("erdnuesse")
    if norm in NUT_ALLERGEN_SESAM:
        out.append("sesam")
    if norm in DAIRY_PROTEIN:
        out.append("milch")
    if norm in SELLERIE_SET:
        out.append("sellerie")
    if norm in SENF_SET:
        out.append("senf")
    return sorted(set(out))


def main():
    raw = json.loads(RAW.read_text(encoding="utf-8"))["rezepte"]
    existing = json.loads(EXISTING_INGREDIENTS.read_text(encoding="utf-8"))
    existing_names = {normalize_name(i["name"]) for i in existing}

    # Pass 1: Einheiten je (normalisierter) Zutat sammeln, um Basiseinheit zu bestimmen
    # (nur Zutaten, die ausschließlich per "Prise" vorkommen, bekommen keine Stimme -> Default übers Kategorie-Fallback)
    unit_votes: dict[str, Counter] = {}
    kat_of: dict[str, str] = {}
    for r in raw:
        for z in r["zutaten"]:
            name = NAME_ALIAS.get(z["name"], z["name"])
            norm = normalize_name(name)
            unit = UNIT_MAP[z["einheit"]]
            conv_qty = GRAM_CONVERT.get((norm, unit))
            effective_unit = "g" if conv_qty is not None else unit
            bucket = UNIT_BUCKET[effective_unit]
            unit_votes.setdefault(norm, Counter())
            if bucket:
                unit_votes[norm][bucket] += 1
            kat_of[norm] = z.get("zutat_kategorie") or "Gemüse"

    new_ingredients = []
    for norm, votes in sorted(unit_votes.items()):
        if norm in existing_names:
            continue
        kat = kat_of[norm]
        base = votes.most_common(1)[0][0] if votes else next(iter(CATEGORY_DEFAULT.get(kat, {"kg": None})))
        price = MANUAL_PRICE.get(norm)
        if price is None:
            table = CATEGORY_DEFAULT.get(kat, {})
            price = table.get(base) or next(iter(table.values()), (199, 249, 399))
        discount, standard, bio = price
        entry = {
            "name": norm,
            "base_unit": base,
            "prices": {"discount": discount, "standard": standard, "bio": bio},
        }
        al = allergens_for(norm)
        if al:
            entry["allergens"] = al
        new_ingredients.append(entry)

    merged_ingredients = existing + new_ingredients

    # Pass 2: Rezepte ins RecipeIn-Schema übersetzen
    out_recipes = []
    seen_slugs: Counter = Counter()
    for r in raw:
        db = r["diaet_basis"]
        assert db["fleischfrei"] and db["fischfrei"], r["name"]  # Annahme fürs vegetarisch-Tag prüfen

        ingredients = []
        for z in r["zutaten"]:
            name = NAME_ALIAS.get(z["name"], z["name"])
            norm = normalize_name(name)
            unit = UNIT_MAP[z["einheit"]]
            conv = GRAM_CONVERT.get((norm, unit))
            if conv is not None:
                ingredients.append({
                    "name": name, "quantity": round(z["menge"] * conv, 1), "unit": "g",
                    "note": f"ca. {z['menge']} {z['einheit']}",
                })
            else:
                ingredients.append({"name": name, "quantity": z["menge"], "unit": unit})

        steps = [{"text": s} for s in r["zubereitung"]]
        tm = r.get("thermomix_variante") or {}
        if tm.get("verfuegbar") and tm.get("hinweis"):
            steps.append({"text": f"Thermomix-Variante: {tm['hinweis']}", "appliance": "thermomix"})

        tags = {t.lower() for t in r.get("tags", [])}
        tags.add("vegetarisch")
        if r.get("vegan"):
            tags.add("vegan")

        appliances = sorted({APPLIANCE_MAP[g] for g in r.get("benoetigte_geraete", [])})
        allergens = sorted({ALLERGEN_MAP[a] for a in r.get("allergene_enthalten", [])})
        meal_types = KATEGORIE_MEAL.get(r["kategorie"], [])

        slug = slugify(r["name"])
        seen_slugs[slug] += 1
        if seen_slugs[slug] > 1:
            slug = f"{slug}-{seen_slugs[slug]}"

        dauer = r["zubereitungsdauer_min"]
        nw = r.get("naehrwerte_pro_portion_geschaetzt") or {}
        out_recipes.append({
            "slug": slug,
            "title": r["name"],
            "summary": f"{r['kategorie']} ({r['kueche']})",
            "servings": r["portionen"],
            "prep_minutes": 0,
            "cook_minutes": dauer["aktiv"],
            "passive_minutes": dauer["passiv"],
            "kcal": nw.get("kalorien_kcal"),
            "protein_g": nw.get("protein_g"),
            "fat_g": nw.get("fett_g"),
            "carbs_g": nw.get("kohlenhydrate_g"),
            "appliances": appliances,
            "allergens": allergens,
            "tags": sorted(tags),
            "meal_types": meal_types,
            "ingredients": ingredients,
            "steps": steps,
        })

    OUT_RECIPES.write_text(json.dumps(out_recipes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_INGREDIENTS.write_text(json.dumps(merged_ingredients, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rezepte: {len(out_recipes)} -> {OUT_RECIPES}")
    print(f"Zutaten: {len(existing)} bestehend + {len(new_ingredients)} neu = {len(merged_ingredients)} -> {OUT_INGREDIENTS}")


if __name__ == "__main__":
    main()
