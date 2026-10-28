#!/usr/bin/env python3
"""Übersetzt Rezepte/rezepte_block_*.json (freier Fließtext: Zutaten als String-Liste,
Zubereitung als ein Absatz) ins RecipeIn-Importschema und erweitert den Zutatenkatalog.

Anders als transform_to_recipein.py (strukturiertes Generator-Format) muss hier aus
Freitext geparst werden: Menge+Einheit+Name aus einem String, Schritte aus einem Absatz.
ponytail: Preis-Konstanten sind bewusst aus transform_to_recipein.py dupliziert statt
importiert, weil dessen Modul beim Import sys.argv liest (CLI-Skript, keine Bibliothek)."""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAW_DIR = Path(sys.argv[1])
EXISTING_INGREDIENTS = Path(sys.argv[2])
OUT_RECIPES = Path(sys.argv[3])
OUT_INGREDIENTS = Path(sys.argv[4])

# ---------- Preis-/Allergen-Konstanten (Basis aus transform_to_recipein.py) ----------

NUT_ALLERGEN_TREE = {
    "cashewkerne", "walnüsse", "haselnüsse", "mandeln", "mandelmehl", "mandelmus", "pekannüsse",
    "pinienkerne", "mandelblättchen", "gemahlene mandeln",
}
NUT_ALLERGEN_PEANUT = {"erdnüsse", "erdnussmus"}
NUT_ALLERGEN_SESAM = {"sesam", "sesamöl", "tahin", "tahini"}
DAIRY_PROTEIN = {
    "feta laktosefrei", "frischkäse laktosefrei", "laktosefreier frischkäse", "laktosefreier gorgonzola",
    "laktosefreier hartkäse", "laktosefreier joghurt", "laktosefreier mozzarella", "laktosefreier parmesan",
    "laktosefreier ricotta", "laktosefreier schmelzkäse", "laktosefreie sahne", "laktosefreie milch",
    "butter laktosefrei", "laktosefreier quark", "laktosefreier skyr", "schlagsahne laktosefrei",
    "joghurt laktosefrei",
}
SELLERIE_SET = {"sellerie", "knollensellerie", "sellerie stange"}
SENF_SET = {"senf", "dijon-senf", "senf glutenfrei"}

CATEGORY_DEFAULT = {
    "Gemüse": {"kg": (199, 249, 399), "stk": (40, 55, 90)},
    "Obst": {"kg": (249, 349, 499), "stk": (40, 60, 90)},
    "Gewürz/Kräuter": {"kg": (1500, 2000, 3000), "l": (1500, 2000, 3000), "stk": (40, 60, 90)},
    "Fett/Öl": {"l": (900, 1100, 1500), "kg": (900, 1100, 1500)},
    "Getreide/Stärke": {"kg": (250, 330, 499), "stk": (150, 200, 300)},
    "Flüssigkeit": {"l": (80, 150, 250)},
    "Hülsenfrucht/Protein": {"kg": (300, 380, 550), "stk": (25, 30, 45)},
    "Milchprodukt": {"kg": (600, 800, 1100), "l": (150, 200, 280)},
    "Milchprodukt (laktosefrei)": {"kg": (1200, 1600, 2200), "l": (250, 330, 450)},
    "Käse": {"kg": (1400, 1800, 2600)},
    "Fleisch": {"kg": (900, 1200, 1800), "stk": (250, 350, 550)},
    "Geflügel": {"kg": (700, 900, 1400), "stk": (250, 350, 550)},
    "Fisch": {"kg": (1800, 2400, 3400), "stk": (350, 450, 650)},
    "Sauce/Paste": {"l": (400, 500, 700), "kg": (400, 500, 700)},
    "Säure/Topping": {"l": (300, 400, 600), "kg": (300, 400, 600)},
    "Nuss/Kern": {"kg": (1200, 1600, 2200)},
    "Süße": {"kg": (600, 900, 1300), "l": (600, 900, 1300)},
}

MANUAL_PRICE = {
    # --- aus Batch 1 (gemeinsame Zutaten, Werte uebernommen fuer Konsistenz) ---
    "zwiebel": (25, 35, 55), "rote zwiebel": (25, 35, 55), "karotte": (129, 169, 269),
    "knoblauch": (10, 12, 20), "knoblauchzehe": (10, 12, 20), "ingwer": (15, 20, 30),
    "kartoffel": (99, 139, 249), "süßkartoffel": (249, 299, 449), "tomate": (35, 45, 70),
    "tomaten": (249, 299, 449), "gurke": (60, 80, 120), "zucchini": (70, 90, 140),
    "paprika": (60, 80, 120), "rote paprika": (60, 80, 120), "grüne paprika": (60, 80, 120),
    "blumenkohl": (199, 249, 399), "brokkoli": (249, 299, 449), "spinat": (399, 499, 699),
    "blattspinat": (399, 499, 699), "champignons": (499, 599, 899), "rote bete": (199, 249, 399),
    "rotkohl": (149, 199, 349), "rotkohl fertig": (199, 249, 399), "lauch": (150, 200, 300),
    "sellerie": (150, 200, 300), "knollensellerie": (199, 249, 399), "fenchel": (90, 120, 180),
    "fenchelknolle": (90, 120, 180), "mais": (299, 349, 499), "maiskolben": (60, 80, 120),
    "kichererbsen": (300, 380, 550), "kidneybohnen": (300, 380, 550), "schwarze bohnen": (300, 380, 550),
    "weiße bohnen": (300, 380, 550), "linsen": (299, 379, 549), "rote linsen": (249, 329, 499),
    "reis": (199, 249, 399), "quinoa": (899, 1099, 1499), "hirse": (349, 449, 649),
    "glutenfreie haferflocken": (399, 499, 699), "haferflocken": (249, 329, 449),
    "honig": (1400, 1800, 2600), "zitrone": (35, 45, 70), "zitronensaft": (500, 700, 1000),
    "limette": (40, 50, 80), "avocado": (90, 120, 180), "apfel": (30, 40, 60), "banane": (20, 25, 40),
    "kokosmilch": (330, 450, 600), "basilikum": (10, 15, 25), "petersilie": (10, 15, 25),
    "dill": (10, 15, 25), "koriander": (10, 15, 25), "minze": (10, 15, 25), "schnittlauch": (10, 15, 25),
    "rosmarin": (10, 15, 25), "majoran": (10, 15, 25), "thymian": (10, 15, 25), "lorbeer": (10, 15, 25),
    "lorbeerblatt": (10, 15, 25), "muskat": (3000, 4000, 6000), "zimt": (1500, 2000, 3000),
    "zimtstange": (30, 40, 60), "sternanis": (30, 40, 60), "fenchelsamen": (1500, 2000, 3000),
    "ras el-hanout": (1800, 2500, 3500), "currypulver": (1500, 2000, 3000), "kreuzkümmel": (1500, 2000, 3000),
    "kurkuma": (1500, 2000, 3000), "paprikapulver": (1200, 1600, 2500), "paprikapulver edelsüß": (1200, 1600, 2500),
    "chilipulver": (1800, 2500, 3500), "oregano": (1500, 2000, 3000), "knoblauchpulver": (1500, 2000, 3000),
    "meerrettich": (1200, 1600, 2200), "chiasamen": (1600, 2000, 2600), "tahin": (1100, 1400, 1800),
    "tahini": (1100, 1400, 1800),
    "laktosefreier joghurt": (350, 450, 650), "laktosefreier quark": (350, 450, 650),
    "laktosefreier skyr": (450, 550, 750), "feta laktosefrei": (1800, 2200, 2800),
    "schlagsahne laktosefrei": (350, 450, 650), "joghurt laktosefrei": (350, 450, 650),
    "butter laktosefrei": (1600, 2000, 2800),
    # --- neu fuer diese Charge: Fleisch/Geflügel ---
    "hähnchenbrust": (799, 999, 1499), "hähnchenschnitzel": (799, 999, 1499),
    "hähnchenkeule": (499, 649, 999), "hähnchenschenkel": (499, 649, 999),
    "hähnchenflügel": (499, 649, 999), "hähnchenhack": (699, 899, 1399),
    "putenbrust": (999, 1299, 1799), "putenschnitzel": (999, 1299, 1799), "putenhack": (799, 999, 1399),
    "putenbraten": (999, 1299, 1799), "rinderhack": (999, 1299, 1799), "rinderfilet": (2999, 3999, 5999),
    "rindersteak": (2499, 3299, 4999), "rinderlendensteak": (2499, 3299, 4999), "rinderbraten": (1499, 1899, 2699),
    "rinderbrust": (1299, 1699, 2399), "rindergulasch": (1499, 1899, 2699), "rinderhüfte": (1699, 2199, 2999),
    "rindersteifen": (1699, 2199, 2999), "rinderstreifen": (1699, 2199, 2999), "rindfleisch wade": (1299, 1699, 2399),
    "lammkotelett": (1999, 2599, 3599), "lammhackfleisch": (1499, 1899, 2699),
    "entenbrust": (1999, 2499, 3499), "schweinefilet": (999, 1299, 1799), "schweinelende": (999, 1299, 1799),
    "schweineschulter": (699, 899, 1399), "speck": (1299, 1599, 2299), "speckwürfel": (1299, 1599, 2299),
    "kochschinken": (1499, 1899, 2699),
    # --- neu: Fisch/Meeresfrüchte ---
    "lachsfilet": (1999, 2499, 3499), "räucherlachs": (2999, 3699, 4999), "thunfisch": (1499, 1899, 2699),
    "kabeljaufilet": (1799, 2299, 3199), "seelachsfilet": (1399, 1799, 2499), "forellenfilet": (1799, 2299, 3199),
    "räucherfisch": (2499, 2999, 3999), "garnelen": (2499, 3199, 4499),
    # --- neu: Käse/Milchprodukte (nicht laktosefrei) ---
    "parmesan": (2200, 2800, 3800), "mozzarella": (1400, 1800, 2400), "feta": (1400, 1800, 2400),
    "ricotta": (1200, 1500, 2000), "hüttenkäse": (900, 1200, 1700), "emmentaler": (1600, 2000, 2600),
    "cheddar": (1800, 2200, 3000), "gouda": (1200, 1500, 2000), "schmelzkäse": (1400, 1800, 2400),
    "hartkäse": (1600, 2000, 2600), "magerquark": (450, 550, 750), "quark": (450, 550, 750),
    "joghurt": (350, 450, 650), "naturjoghurt": (350, 450, 650), "griechischer joghurt": (550, 700, 950),
    "skyr": (450, 550, 750), "sahne": (300, 400, 600), "hafersahne": (300, 400, 600), "schmand": (300, 400, 550),
    "crème fraîche": (500, 650, 900), "frischkäse": (900, 1200, 1700), "butter": (1600, 2000, 2800),
    "milch": (120, 150, 200), "mandelmilch": (250, 330, 450), "hafermilch": (150, 200, 280),
    # --- neu: Getreide/Backwaren/Sonstiges ---
    "mehl": (150, 200, 300), "dinkelmehl": (249, 349, 499), "buchweizen": (349, 449, 649),
    "bulgur": (299, 399, 549), "linguine": (199, 249, 399), "vollkornnudeln": (249, 349, 499),
    "vollkornpasta": (249, 349, 499), "eiernudeln": (299, 399, 549), "nudeln": (199, 249, 399),
    "glasnudeln": (399, 499, 699), "vollkornbrot": (299, 349, 499), "vollkornbrötchen": (40, 55, 80),
    "vollkornfladen": (60, 80, 120), "vollkornbagel": (70, 90, 140), "ciabatta-brötchen": (50, 70, 100),
    "toastbrot": (199, 249, 349), "pita-brote": (60, 80, 120), "weizentortillas": (250, 330, 450),
    "vollkorn-wraps": (300, 400, 550), "glutenfreie wraps": (400, 500, 700),
    "glutenfreie maistortillas": (250, 330, 450), "glutenfreie burgerbrötchen": (80, 110, 160),
    "glutenfreies brot": (349, 449, 649), "vollkorn-pizzateig": (249, 299, 399),
    "sushireis": (299, 349, 499), "semmelbrösel": (299, 399, 549), "speisestärke": (199, 249, 349),
    "puderzucker": (249, 299, 399), "zucker": (99, 149, 249), "backpulver": (600, 800, 1200),
    "ketchup": (300, 400, 600), "sojasauce": (600, 800, 1200), "austernsauce": (900, 1200, 1700),
    "fischsauce": (900, 1200, 1700), "bbq-sauce": (600, 800, 1200), "balsamico": (700, 900, 1300),
    "apfelessig": (400, 500, 700), "essig": (300, 400, 600), "weißweinessig": (400, 500, 700),
    "weißwein": (500, 700, 1000), "tomatenmark": (300, 400, 600), "passierte tomate": (249, 299, 449),
    "hummus": (700, 900, 1300), "tempeh": (599, 799, 1099), "miso-paste": (900, 1200, 1700),
    "kokosaminos": (1800, 2200, 2900), "pesto": (900, 1200, 1700), "salsa": (500, 700, 1000),
    "edamame": (599, 799, 1099), "mungbohnen": (399, 499, 699), "mungbohnensprossen": (399, 499, 699),
    "gelbe schälerbsen": (299, 379, 549), "sojagranulat": (599, 799, 1099), "polenta": (249, 299, 449),
    "crème fraîche light": (500, 650, 900),
}

ALLERGEN_MAP = {
    "ei": "eier", "milch": "milch", "gluten": "gluten", "fisch": "fisch", "sesam": "sesam",
    "schalentiere": "krebstiere", "senf": "senf", "soja": "soja", "nüsse": "schalenfruechte",
    "erdnüsse": "erdnuesse",
}

APPLIANCE_MAP = {"Herd": "herd", "Pfanne": "herd", "Backofen": "backofen", "Thermomix": "thermomix",
                  "Waffeleisen": "waffeleisen"}

BREAKFAST_TITLE_KEYWORDS = ["frühstück", "pancake", "porridge", "smoothie", "müsli", "overnight",
                             "rührei", "omelett", "granola", "waffel", "french toast"]

MEAT_FISH_WORDS = {
    "hähnchenbrust", "hähnchenschnitzel", "hähnchenkeule", "hähnchenschenkel", "hähnchenflügel",
    "hähnchenhack", "putenbrust", "putenschnitzel", "putenhack", "putenbraten", "rinderhack",
    "rinderfilet", "rindersteak", "rinderlendensteak", "rinderbraten", "rinderbrust", "rindergulasch",
    "rinderhüfte", "rinderstreifen", "rindfleisch wade", "lammkotelett", "lammhackfleisch", "entenbrust",
    "schweinefilet", "schweinelende", "schweineschulter", "speck", "speckwürfel", "kochschinken",
    "lachsfilet", "räucherlachs", "thunfisch", "kabeljaufilet", "seelachsfilet", "forellenfilet",
    "räucherfisch", "garnelen", "lachs", "forelle",
}
DAIRY_EGG_WORDS = {
    "ei", "eier", "eigelb", "milch", "quark", "magerquark", "joghurt", "naturjoghurt",
    "griechischer joghurt", "skyr", "sahne", "hafersahne", "schmand", "crème fraîche", "frischkäse",
    "butter", "parmesan", "mozzarella", "feta", "ricotta", "hüttenkäse", "emmentaler", "cheddar",
    "gouda", "schmelzkäse", "hartkäse", "honig",
}
PLANT_MILK_WORDS = {"hafermilch", "mandelmilch", "kokosmilch", "sojamilch", "hafersahne", "kokosaminos"}

TRUE_UNITS = {
    "g": "g", "kg": "kg", "ml": "ml", "l": "l", "el": "el", "tl": "tl", "prise": "prise",
    "stück": "stk", "stk": "stk",
    "scheibe": ("stk", "Scheibe"), "scheiben": ("stk", "Scheibe"),
    "stange": ("stk", "Stange"), "stangen": ("stk", "Stange"),
    "zweig": ("stk", "Zweig"), "zweige": ("stk", "Zweig"),
    "dose": "__dose__", "dosen": "__dose__",
}

PLURAL_TO_SINGULAR = {
    "äpfel": "apfel", "auberginen": "aubergine", "bananen": "banane", "chilis": "chili",
    "eier": "ei", "entenbrüste": "entenbrust", "forellenfilets": "forellenfilet",
    "frühlingszwiebeln": "frühlingszwiebel", "gurken": "gurke", "karotten": "karotte",
    "kartoffeln": "kartoffel", "knoblauchzehen": "knoblauchzehe", "limetten": "limette",
    "orangen": "orange", "pastinaken": "pastinake", "pflaumen": "pflaume",
    "süßkartoffeln": "süßkartoffel", "zwiebeln": "zwiebel",
    "blumenköpfe": "blumenkohl", "blumenkopf": "blumenkohl",
}
# "Tomaten" bleibt bei Gewichtsangaben (400 g Tomaten/passierte Tomaten) absichtlich Plural,
# um die bestehende kg-Katalogzutat "tomaten" zu treffen; nur bei Stückzahl ("2 Tomaten")
# ist die Einzeltomate ("tomate", stk-Katalog) gemeint, siehe Stückzahl-Zweig in parse_line.
BARE_COUNT_ALIAS = {"tomaten": "tomate"}

# Zutat (normalisiert) + abweichende Rezept-Einheit -> Gramm, damit alle Verwendungen einer
# Zutat auf die EINE Katalog-Basiseinheit (meist kg) zusammenlaufen statt eine Dublette mit
# anderer Basiseinheit zu erzeugen (siehe Karotte/Zwiebel-Fix aus Batch 1).
# ponytail: grobe Schätzung, kein Anspruch auf Präzision.
GRAM_CONVERT = {
    ("zwiebel", "stk"): 120.0, ("karotte", "stk"): 80.0, ("blumenkohl", "stk"): 900.0,
    ("rote bete", "stk"): 120.0, ("chiasamen", "el"): 12.0, ("currypulver", "tl"): 3.0,
    ("erdnüsse", "el"): 10.0, ("mandelmus", "el"): 15.0, ("dill", "tl"): 1.0, ("minze", "el"): 3.0,
    ("salz", "prise"): 0.3, ("salz", "tl"): 5.0,
    ("kartoffel", "stk"): 150.0, ("süßkartoffel", "stk"): 250.0,
    ("haferflocken (glutenfrei)", "el"): 10.0, ("joghurt (10 %)", "el"): 15.0,
    ("kürbiskerne", "el"): 10.0, ("walnüsse", "el"): 10.0, ("mehl", "el"): 10.0,
    ("frischkäse (light)", "el"): 15.0, ("mandelblättchen", "el"): 8.0,
    ("butter", "el"): 15.0, ("butter", "tl"): 5.0, ("semmelbrösel", "el"): 8.0,
    # Fleisch/Fisch/Käse, die hier ueberwiegend stückweise genannt werden, aber in
    # MANUAL_PRICE als kg-Preis hinterlegt sind -> auf Gramm vereinheitlichen, sonst
    # würde der kg-Preis faelschlich als Stück-Preis verwendet (z.B. 13€ pro Schnitzel).
    ("putenschnitzel", "stk"): 150.0, ("hähnchenschnitzel", "stk"): 150.0,
    ("forellenfilet", "stk"): 150.0, ("cheddar (scheibe)", "stk"): 20.0,
    ("hähnchenschenkel", "stk"): 250.0, ("weizentortillas", "stk"): 40.0,
    ("vollkorn-wraps", "stk"): 60.0, ("glutenfreie wraps", "stk"): 60.0,
    ("glutenfreie maistortillas", "stk"): 30.0,
}

NAME_ALIAS = {"tomate (dose)": "tomaten", "tomaten (dose)": "tomaten"}

# ---------- Parsing ----------

STRIP_WORDS = {
    "groß", "große", "großer", "großes", "kleiner", "kleine", "kleines", "mittelgroß", "mittelgroße",
    "dünn", "dünne", "dünner", "ganze", "ganzer", "ganzes", "fein", "feine", "grob", "grobe",
    "roh", "rohe", "gekocht", "gekochte", "gekochter", "gegart", "gegarte", "vorgegart", "vorgegarte",
    "ausgedampft", "geschält", "geschälte", "gewaschen", "gereinigt", "geputzt", "gerieben", "geriebene",
    "geriebener", "gehackt", "gehackte", "zerdrückt", "zerdrückte", "püriert", "pürierte", "warm",
    "gewürfelt", "gewürfelte", "geschnitten", "aufgeschnitten", "abgeschnitten", "ausgenommen",
    "geschmolzen", "zum", "garen", "braten", "frittieren", "prüfen", "noch", "sushi-qualität",
}
STRIP_PHRASES = ["in scheiben", "dünn geschnitten", "fein gewürfelt", "fein gehackt", "grob gehackt",
                 "fein gerieben", "roh, gerieben", "dünn geklopft"]


def split_top_commas(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        if ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _strip_descriptors(text):
    for p in STRIP_PHRASES:
        text = re.sub(re.escape(p), "", text, flags=re.I)
    tokens = re.split(r"(\s+|,|\(|\))", text)
    out = [t for t in tokens if t.strip().lower().strip(",") not in STRIP_WORDS]
    text = "".join(out)
    text = re.sub(r"\(\s*,*\s*\)", "", text)
    text = re.sub(r",\s*\)", ")", text)
    text = re.sub(r"\(\s*,", "(", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def normalize_name(name):
    name = _strip_descriptors(re.sub(r"\s+", " ", name.strip()))
    words = [PLURAL_TO_SINGULAR.get(w.lower(), w.lower()) for w in name.split(" ")]
    name = " ".join(w for w in words if w)
    return NAME_ALIAS.get(name, name)


def slugify(text):
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:150]


def allergens_for(norm):
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


QTY_RE = re.compile(r"^\s*(\d+/\d+|\d+(?:[.,]\d+)?)\s*(.*)$")


def parse_dose_weight(rest):
    m = re.search(r"\((?:je\s+)?(\d+)\s*g([^)]*)\)", rest)
    if not m:
        return 400.0, rest
    weight = float(m.group(1))
    tail = m.group(2).strip(" ,")
    name = rest[: m.start()].strip()
    return weight, (f"{name} ({tail})" if tail else name)


def parse_qty(qty_str):
    if "/" in qty_str:
        a, b = qty_str.split("/")
        return float(a) / float(b)
    return float(qty_str.replace(",", "."))


def parse_line(line):
    """-> Liste von (name, qty|None, unit|None, note|None)"""
    m = QTY_RE.match(line)
    if not m:
        out = []
        for part in split_top_commas(line):
            part = re.sub(r"^(etwas|wenig|paar)\s+", "", part, flags=re.I).strip()
            if part:
                out.append((normalize_name(part), None, None, None))
        return out

    qty_str, rest = m.groups()
    qty = parse_qty(qty_str)
    rest = rest.strip()
    fw = re.match(r"^(\S+)(?:\s+(.*))?$", rest)
    first_word, remainder = fw.group(1), (fw.group(2) or "")
    unit_info = TRUE_UNITS.get(first_word.lower().rstrip("."))

    if unit_info is None:
        name = normalize_name(rest)
        name = BARE_COUNT_ALIAS.get(name, name)
        conv = GRAM_CONVERT.get((name, "stk"))
        if conv is not None:
            return [(name, round(qty * conv, 1), "g", f"ca. {qty_str} Stück")]
        return [(name, qty, "stk", None)]

    if unit_info == "__dose__":
        weight, new_name = parse_dose_weight(remainder)
        name = normalize_name(new_name)
        return [(name, round(qty * weight, 1), "g", f"{qty_str} Dose(n)")]

    if isinstance(unit_info, tuple):
        unit, qualifier = unit_info
        raw_name = remainder.strip()
        if qualifier.lower() not in raw_name.lower():
            raw_name = f"{raw_name} ({qualifier})"
        name = normalize_name(raw_name)
        conv = GRAM_CONVERT.get((name, unit))
        if conv is not None:
            return [(name, round(qty * conv, 1), "g", f"ca. {qty_str} {qualifier}")]
        return [(name, qty, unit, None)]

    name = normalize_name(remainder.strip())
    unit = unit_info
    conv = GRAM_CONVERT.get((name, unit))
    if conv is not None:
        return [(name, round(qty * conv, 1), "g", f"ca. {qty_str} {first_word}")]
    return [(name, qty, unit, None)]


def split_steps(text):
    text = text.strip()
    parts = re.split(r"(?<=[.!])\s+(?=[A-ZÄÖÜ])", text)
    return [p.strip() for p in parts if p.strip()]


def map_allergen(label):
    base = label.split("(")[0].strip().lower()
    if base == "nüsse" and "erdnü" in label.lower():
        return "erdnuesse"
    return ALLERGEN_MAP.get(base)


def word_set(name):
    return set(re.findall(r"[a-zäöüß\-]+", name.lower()))


def guess_tags(ingredient_names):
    words = set()
    for n in ingredient_names:
        words |= word_set(n)
    has_meat_fish = any(w in MEAT_FISH_WORDS or n in MEAT_FISH_WORDS for n in ingredient_names for w in word_set(n))
    has_meat_fish = has_meat_fish or any(n in MEAT_FISH_WORDS for n in ingredient_names)
    if any(n in PLANT_MILK_WORDS for n in ingredient_names):
        dairy_names = [n for n in ingredient_names if n not in PLANT_MILK_WORDS]
    else:
        dairy_names = ingredient_names
    has_dairy_egg = any(n in DAIRY_EGG_WORDS for n in dairy_names)
    if has_meat_fish:
        return []
    if has_dairy_egg:
        return ["vegetarisch"]
    return ["vegetarisch", "vegan"]


def guess_meal_types(title):
    low = title.lower()
    if any(k in low for k in BREAKFAST_TITLE_KEYWORDS):
        return ["fruehstueck"]
    return ["mittag", "abend"]


def guess_category(norm):
    if norm in MANUAL_PRICE:
        for cat, table in CATEGORY_DEFAULT.items():
            pass  # Preis kommt direkt aus MANUAL_PRICE, Kategorie nur für Bucket-Fallback unten
    checks = [
        (("hähnchen", "huhn", "pute", "truthahn", "ente"), "Geflügel"),
        (("rind", "schwein", "lamm", "speck", "schinken", "wurst", "kochschinken"), "Fleisch"),
        (("fisch", "lachs", "thunfisch", "kabeljau", "forelle", "garnele", "seelachs"), "Fisch"),
        (("käse", "parmesan", "mozzarella", "feta", "ricotta", "cheddar", "gouda", "emmentaler"), "Käse"),
        (("milch", "joghurt", "quark", "skyr", "sahne", "schmand", "butter", "créme", "crème"), "Milchprodukt"),
        (("mehl", "nudel", "reis", "brot", "brötchen", "tortilla", "wrap", "bagel", "couscous",
          "polenta", "bröse", "stärke", "teig", "waffel", "flocken"), "Getreide/Stärke"),
        (("öl",), "Fett/Öl"),
        (("zucker", "sirup", "ahorn"), "Süße"),
        (("sauce", "paste", "ketchup", "essig", "mark", "hummus", "pesto", "salsa", "aminos"), "Sauce/Paste"),
        (("nuss", "nüsse", "kern", "mandel", "cashew"), "Nuss/Kern"),
        (("beere", "apfel", "banane", "birne", "orange", "granatapfel", "mango"), "Obst"),
        (("bohne", "linse", "erbse", "edamame", "tempeh", "soja"), "Hülsenfrucht/Protein"),
        (("pulver", "kümmel", "kurkuma", "muskat", "zimt", "anis", "lorbeer", "majoran", "oregano",
          "thymian", "rosmarin", "basilikum", "dill", "koriander", "minze", "schnittlauch", "petersilie",
          "ras el-hanout", "fenchelsamen", "meerrettich"), "Gewürz/Kräuter"),
    ]
    for keys, cat in checks:
        if any(k in norm for k in keys):
            return cat
    return "Gemüse"


def price_for(norm, base, kat):
    if norm in MANUAL_PRICE:
        return MANUAL_PRICE[norm]
    table = CATEGORY_DEFAULT.get(kat, CATEGORY_DEFAULT["Gemüse"])
    return table.get(base) or next(iter(table.values()))


def main():
    raw_recipes = []
    for f in sorted(RAW_DIR.glob("rezepte_block_*.json")):
        raw_recipes.extend(json.loads(f.read_text(encoding="utf-8"))["rezepte"])

    existing = json.loads(EXISTING_INGREDIENTS.read_text(encoding="utf-8"))
    existing_map = {re.sub(r"\s+", " ", i["name"].strip().lower()): i for i in existing}

    # Pass 1: Einheiten-Buckets je Zutat sammeln (für neue Katalogeinträge)
    bucket_of = {"g": "kg", "kg": "kg", "ml": "l", "l": "l", "el": "l", "tl": "l", "stk": "stk"}
    votes: dict[str, Counter] = {}
    for r in raw_recipes:
        for line in r["zutaten"]:
            for name, qty, unit, _ in parse_line(line):
                votes.setdefault(name, Counter())
                if unit and bucket_of.get(unit):
                    votes[name][bucket_of[unit]] += 1

    new_ingredients = []
    for name, counter in sorted(votes.items()):
        if name in existing_map or not name:
            continue
        kat = guess_category(name)
        base = counter.most_common(1)[0][0] if counter else next(iter(CATEGORY_DEFAULT.get(kat, {"kg": None})))
        price = price_for(name, base, kat)
        entry = {"name": name, "base_unit": base, "prices": {"discount": price[0], "standard": price[1], "bio": price[2]}}
        al = allergens_for(name)
        if al:
            entry["allergens"] = al
        new_ingredients.append(entry)
        if base == "stk" and name in MANUAL_PRICE and price[1] > 300:
            print(f"WARNUNG: {name!r} ist stk-basiert, aber MANUAL_PRICE sieht nach kg-Preis aus "
                  f"({price[1]} ct) -> ggf. GRAM_CONVERT ergaenzen.", file=sys.stderr)

    merged_ingredients = existing + new_ingredients
    merged_names = {re.sub(r"\s+", " ", i["name"].strip().lower()) for i in merged_ingredients}

    # Pass 2: Rezepte übersetzen
    out_recipes = []
    seen_slugs: Counter = Counter()
    for other in (EXISTING_INGREDIENTS.parent / "recipes_batch1.json", EXISTING_INGREDIENTS.parent / "recipes.json"):
        if other.exists():
            for r in json.loads(other.read_text(encoding="utf-8")):
                seen_slugs[r["slug"]] += 1
    skipped = []
    for r in raw_recipes:
        ingredients = []
        ingredient_names = []
        for line in r["zutaten"]:
            for name, qty, unit, note in parse_line(line):
                if not name:
                    continue
                entry = {"name": name, "quantity": qty, "unit": unit}
                if note:
                    entry["note"] = note
                ingredients.append(entry)
                ingredient_names.append(name)

        if not ingredients:
            skipped.append(r["id"])
            continue

        steps = [{"text": s} for s in split_steps(r["schritte"])]
        if not steps:
            skipped.append(r["id"])
            continue

        appliances = sorted({APPLIANCE_MAP[g] for g in r.get("geraete", []) if g in APPLIANCE_MAP})
        allergens = sorted({a for a in (map_allergen(x) for x in r.get("allergene", [])) if a})
        tags = guess_tags(ingredient_names)
        meal_types = guess_meal_types(r["titel"])

        slug = slugify(r["titel"])
        seen_slugs[slug] += 1
        if seen_slugs[slug] > 1:
            slug = f"{slug}-{seen_slugs[slug]}"

        out_recipes.append({
            "slug": slug,
            "title": r["titel"],
            "servings": r["portionen"],
            "prep_minutes": 0,
            "cook_minutes": r["dauer_min"],
            "passive_minutes": 0,
            "kcal": r.get("kcal"),
            "protein_g": r.get("protein_g"),
            "fat_g": r.get("fett_g"),
            "carbs_g": r.get("kh_g"),
            "appliances": appliances,
            "allergens": allergens,
            "tags": tags,
            "meal_types": meal_types,
            "ingredients": ingredients,
            "steps": steps,
        })

    OUT_RECIPES.write_text(json.dumps(out_recipes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_INGREDIENTS.write_text(json.dumps(merged_ingredients, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rezepte: {len(out_recipes)} (uebersprungen: {len(skipped)}) -> {OUT_RECIPES}")
    print(f"Zutaten: {len(existing)} bestehend + {len(new_ingredients)} neu = {len(merged_ingredients)} -> {OUT_INGREDIENTS}")
    if skipped:
        print("uebersprungen:", skipped)


if __name__ == "__main__":
    main()
