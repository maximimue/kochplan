#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generiert 200 Rezepte für die Kochplan-App.
Basis-Filter (für ALLE Rezepte fix): glutenfrei, laktosefrei, fleischfrei, fischfrei, sojafrei.
Zusätzlich werden weitere Allergene/Eigenschaften automatisch aus den Zutaten abgeleitet,
damit die App danach filtern/sortieren kann (Nüsse, Sesam, Senf, Sellerie, Ei, Milcheiweiß, vegan ja/nein).
"""
import json, re, unicodedata

# ---------------------------------------------------------------------------
# 1) Allergen-Erkennung (Keyword -> Allergen-Tag)
# ---------------------------------------------------------------------------
ALLERGEN_KEYWORDS = {
    "Nüsse": ["mandel", "cashew", "walnuss", "haselnuss", "pistazie", "pekannuss", "macadamia", "pinienkern"],
    "Erdnuss": ["erdnuss"],
    "Sesam": ["sesam", "tahini", "za'atar", "zaatar"],
    "Senf": ["senf"],
    "Sellerie": ["sellerie"],
    "Ei": ["ei", "eier", "eigelb", "eiweiß"],
    "Milcheiweiß": ["käse", "joghurt", "sahne", "butter", "frischkäse", "quark", "milch", "feta", "parmesan", "pecorino", "mozzarella", "gorgonzola", "ricotta"],
    "Lupinen": ["lupine"],
}

def normalize(s):
    s = s.lower().replace("ß", "ss")
    decomposed = unicodedata.normalize("NFKD", s)
    # Kombinierende Umlaut-Zeichen entfernen (ü -> u, ö -> o, ä -> a), damit
    # z.B. "Walnüsse" und "walnuss" denselben Wortstamm "walnu.." ergeben.
    return "".join(c for c in decomposed if not unicodedata.combining(c))

def detect_allergens(ingredient_names):
    found = set()
    # Wortgrenzen-basiertes Matching, damit z.B. "eier" nicht fälschlich in
    # "laktosefreier" erkannt wird.
    texts = [normalize(n) for n in ingredient_names]
    for tag, keywords in ALLERGEN_KEYWORDS.items():
        for kw in keywords:
            if not kw:
                continue
            # Nur führende Wortgrenze: erlaubt Komposita/Plural (z.B. "Mandelmehl",
            # "Erdnüsse"), verhindert aber Treffer mitten im Wort wie "eier" in
            # "laktosefreier" (dort steht vor "ei" kein Wortgrenzen-Übergang).
            pattern = r"\b" + re.escape(kw)
            if any(re.search(pattern, t) for t in texts):
                found.add(tag)
                break
    return sorted(found)

def is_vegan(ingredient_names, allergens):
    if "Ei" in allergens or "Milcheiweiß" in allergens:
        return False
    text = " ".join(normalize(n) for n in ingredient_names)
    if "honig" in text:
        return False
    return True

# ---------------------------------------------------------------------------
# 2) Bausteine je Rezept-Kategorie
#    Jede Kategorie liefert eine Liste "Varianten" mit konkreten, echten
#    Kombinationen (keine beliebige Zufallsmischung) -> kulinarisch sinnvoll.
# ---------------------------------------------------------------------------

recipes = []
rid = 1

def add_recipe(name, kategorie, kueche, geraete, zeit_aktiv, zeit_passiv, schwierigkeit,
                portionen, zutaten, zubereitung, kosten_kat, kcal, protein, fett, kh, ballaststoffe,
                tags=None, thermomix=None):
    global rid
    ing_names = [z["name"] for z in zutaten]
    allergene = detect_allergens(ing_names)
    vegan = is_vegan(ing_names, allergene)
    rec = {
        "id": f"R{rid:03d}",
        "name": name,
        "kategorie": kategorie,
        "kueche": kueche,
        "diaet_basis": {
            "glutenfrei": True,
            "laktosefrei": True,
            "fleischfrei": True,
            "fischfrei": True,
            "sojafrei": True
        },
        "vegan": vegan,
        "allergene_enthalten": allergene,
        "portionen": portionen,
        "zubereitungsdauer_min": {
            "aktiv": zeit_aktiv,
            "passiv": zeit_passiv,
            "gesamt": zeit_aktiv + zeit_passiv
        },
        "schwierigkeit": schwierigkeit,
        "benoetigte_geraete": geraete,
        "thermomix_variante": thermomix if thermomix else {"verfuegbar": False},
        "kosten_schaetzung": {
            "kategorie": kosten_kat,
            "ca_eur_pro_portion": {"günstig": 1.8, "mittel": 3.2, "hochwertig": 5.5}[kosten_kat]
        },
        "naehrwerte_pro_portion_geschaetzt": {
            "kalorien_kcal": kcal, "protein_g": protein, "fett_g": fett,
            "kohlenhydrate_g": kh, "ballaststoffe_g": ballaststoffe
        },
        "zutaten": zutaten,
        "zubereitung": zubereitung,
        "tags": tags or [],
        "quelle": "fest"
    }
    recipes.append(rec)
    rid += 1
    return rec

def z(name, menge, einheit, kat):
    return {"name": name, "menge": menge, "einheit": einheit, "zutat_kategorie": kat}

# ---------------------------------------------------------------------------
# Hilfsdaten
# ---------------------------------------------------------------------------
GEMUESE_SCHNEIDEN = "{gemuese} waschen und in mundgerechte Stücke schneiden."

def steps_pfanne(intro_fett, hauptzutaten_text, wuerzung_text, fluessigkeit_text, servier_text):
    return [
        f"Gemüse waschen, putzen und in mundgerechte Stücke schneiden.",
        f"{intro_fett} in einer großen Pfanne erhitzen.",
        f"{hauptzutaten_text} darin bei mittlerer bis hoher Hitze 5–8 Minuten anbraten, gelegentlich wenden.",
        f"{wuerzung_text} zugeben, kurz mitrösten bis es duftet.",
        f"{fluessigkeit_text} angießen, 5–10 Minuten köcheln lassen, bis alles gar und die Sauce leicht eingedickt ist.",
        f"Abschmecken und {servier_text}."
    ]

def steps_suppe(fett_text, anschwitzen_text, fluessigkeit_text, kochzeit, puerier, servier_text):
    s = [
        "Zwiebel und Knoblauch fein hacken, restliches Gemüse grob würfeln.",
        f"{fett_text} im Topf erhitzen, {anschwitzen_text} darin 3–4 Minuten andünsten.",
        f"{fluessigkeit_text} angießen, aufkochen und {kochzeit} Minuten köcheln lassen, bis das Gemüse weich ist.",
    ]
    if puerier:
        s.append("Mit dem Stabmixer fein pürieren (für eine stückige Variante nur teilweise pürieren).")
    s.append(f"Mit Salz, Pfeffer und den angegebenen Gewürzen abschmecken und {servier_text}.")
    return s

def steps_salat(dressing_text, servier_text):
    return [
        "Alle Salat-Zutaten waschen, putzen und in mundgerechte Stücke schneiden bzw. Hülsenfrüchte abtropfen lassen.",
        "Für das Dressing alle Dressing-Zutaten in einem kleinen Glas oder Schüssel glattrühren.",
        f"{dressing_text}",
        "Zutaten in einer großen Schüssel vermengen und das Dressing darüber geben.",
        f"Vorsichtig durchmischen, kurz ziehen lassen und {servier_text}."
    ]

def steps_curry(basis_text, gewuerz_text, kokos_text, gemuese_text, kochzeit, servier_text):
    return [
        "Zwiebel, Knoblauch und Ingwer fein hacken, restliches Gemüse in Stücke schneiden.",
        f"{basis_text} im Topf erhitzen, Zwiebel, Knoblauch und Ingwer darin andünsten.",
        f"{gewuerz_text} zugeben und kurz mitrösten, bis es duftet.",
        f"{gemuese_text} dazugeben und kurz mit anbraten.",
        f"{kokos_text} angießen, aufkochen, dann {kochzeit} Minuten bei milder Hitze köcheln lassen, bis das Gemüse gar ist.",
        f"Abschmecken und {servier_text}."
    ]

def steps_ofen(vorbereiten_text, fuellen_text, ofenzeit, temperatur, servier_text):
    return [
        "Ofen auf {}°C Ober-/Unterhitze vorheizen.".format(temperatur),
        f"{vorbereiten_text}",
        f"{fuellen_text}",
        f"Im Ofen {ofenzeit} Minuten backen, bis alles gar ist und eine leicht goldene Oberfläche hat.",
        f"Kurz ruhen lassen und {servier_text}."
    ]

def steps_pasta(nudelsorte, sauce_text, kochzeit_nudeln, servier_text):
    return [
        f"{nudelsorte} nach Packungsangabe (ca. {kochzeit_nudeln} Minuten) in reichlich Salzwasser bissfest kochen, dabei eine Tasse Nudelwasser zurückbehalten.",
        f"{sauce_text}",
        "Abgetropfte Nudeln zur Sauce geben, bei Bedarf etwas Nudelwasser zum Binden unterrühren.",
        f"Kurz durchschwenken, abschmecken und {servier_text}."
    ]

def steps_fruehstueck(zubereiten_text, kochzeit_text, servier_text):
    return [
        f"{zubereiten_text}",
        f"{kochzeit_text}",
        f"{servier_text}"
    ]

def steps_snack(zubereiten_text, garen_text, servier_text):
    return [
        f"{zubereiten_text}",
        f"{garen_text}",
        f"{servier_text}"
    ]

def steps_dessert(zubereiten_text, kuehlen_oder_backen_text, servier_text):
    return [
        f"{zubereiten_text}",
        f"{kuehlen_oder_backen_text}",
        f"{servier_text}"
    ]

# ---------------------------------------------------------------------------
# 3) Genereller Zubereitungs-Generator
#    Jede Zutat trägt eine "zutat_kategorie" (Rolle im Rezept). Daraus baut
#    der Generator pro Rezept-Kategorie eine stimmige Schritt-für-Schritt-
#    Anleitung, ohne für jedes der 200 Rezepte Fließtext von Hand zu pflegen.
# ---------------------------------------------------------------------------
import random

def names_by_role(zutaten, role):
    return [z["name"] for z in zutaten if z["zutat_kategorie"] == role]

def join_de(items):
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " und " + items[-1]

def build_steps(kategorie, zutaten, kueche=""):
    gemuese = join_de(names_by_role(zutaten, "Gemüse"))
    huelsenfrucht = join_de(names_by_role(zutaten, "Hülsenfrucht/Protein"))
    staerke = join_de(names_by_role(zutaten, "Getreide/Stärke"))
    fett = join_de(names_by_role(zutaten, "Fett/Öl")) or "Öl"
    gewuerze = join_de(names_by_role(zutaten, "Gewürz/Kräuter"))
    fluessigkeit = join_de(names_by_role(zutaten, "Flüssigkeit"))
    milchprodukt = join_de(names_by_role(zutaten, "Milchprodukt (laktosefrei)"))
    nuesse = join_de(names_by_role(zutaten, "Nuss/Kern"))
    saeure = join_de(names_by_role(zutaten, "Säure/Topping"))
    suesse = join_de(names_by_role(zutaten, "Süße"))

    if kategorie == "Pfannengericht":
        steps = [f"{gemuese} waschen, putzen und in mundgerechte Stücke schneiden." if gemuese else "Alle Zutaten vorbereiten.",
                 f"{fett.capitalize()} in einer großen Pfanne erhitzen."]
        if huelsenfrucht:
            steps.append(f"{huelsenfrucht} und {gemuese} bei mittlerer bis hoher Hitze 5–8 Minuten anbraten." if gemuese else f"{huelsenfrucht} 5–8 Minuten anbraten.")
        elif gemuese:
            steps.append(f"{gemuese} bei mittlerer bis hoher Hitze 5–8 Minuten anbraten, gelegentlich wenden.")
        if gewuerze:
            steps.append(f"{gewuerze} zugeben und kurz mitrösten, bis es duftet.")
        if fluessigkeit:
            steps.append(f"{fluessigkeit} angießen und 5–10 Minuten köcheln lassen, bis die Sauce leicht eingedickt ist.")
        if staerke:
            steps.append(f"Mit {staerke} als Beilage servieren.")
        finish = []
        if milchprodukt: finish.append(milchprodukt)
        if nuesse: finish.append(nuesse)
        if saeure: finish.append(saeure)
        steps.append(f"Abschmecken, mit {join_de(finish)} vollenden und servieren." if finish else "Abschmecken und servieren.")
        return steps

    if kategorie == "Suppe":
        steps = ["Zwiebel und Knoblauch fein hacken, restliches Gemüse grob würfeln." if gemuese else "Alle Zutaten vorbereiten.",
                 f"{fett.capitalize()} im Topf erhitzen und {gemuese} darin 3–4 Minuten andünsten." if gemuese else f"{fett.capitalize()} im Topf erhitzen."]
        if huelsenfrucht:
            steps.append(f"{huelsenfrucht} zugeben und kurz mit andünsten.")
        if gewuerze:
            steps.append(f"{gewuerze} zugeben, kurz mitrösten.")
        steps.append(f"{fluessigkeit} angießen, aufkochen und 15–20 Minuten köcheln lassen, bis alles weich ist." if fluessigkeit else "Mit Wasser oder Gemüsebrühe auffüllen und 15–20 Minuten köcheln lassen.")
        steps.append("Nach Belieben mit dem Stabmixer ganz oder teilweise fein pürieren.")
        finish = join_de([x for x in [milchprodukt, nuesse, saeure] if x])
        steps.append(f"Abschmecken, mit {finish} anrichten und servieren." if finish else "Abschmecken und heiß servieren.")
        return steps

    if kategorie == "Salat":
        steps = [f"{gemuese} waschen, putzen und in mundgerechte Stücke schneiden." if gemuese else "Salatzutaten vorbereiten."]
        if huelsenfrucht:
            steps.append(f"{huelsenfrucht} abtropfen lassen bzw. nach Packungsangabe vorbereiten.")
        if staerke:
            steps.append(f"{staerke} nach Packungsangabe kochen, abkühlen lassen.")
        dressing_parts = join_de([x for x in [fett, saeure, gewuerze, suesse] if x])
        steps.append(f"Für das Dressing {dressing_parts} verrühren." if dressing_parts else "Ein einfaches Dressing aus Öl, Säure und Gewürzen anrühren.")
        steps.append("Alle Zutaten in einer großen Schüssel vermengen und das Dressing darüber geben.")
        finish = join_de([x for x in [milchprodukt, nuesse] if x])
        steps.append(f"Mit {finish} bestreuen, vorsichtig durchmischen und servieren." if finish else "Vorsichtig durchmischen und servieren.")
        return steps

    if kategorie == "Curry":
        steps = [f"{gemuese} waschen, putzen und in Stücke schneiden." if gemuese else "Alle Zutaten vorbereiten.",
                 f"{fett.capitalize()} im Topf erhitzen."]
        if gewuerze:
            steps.append(f"{gewuerze} zugeben und kurz mitrösten, bis es duftet.")
        main = join_de([x for x in [huelsenfrucht, gemuese] if x])
        if main:
            steps.append(f"{main} dazugeben und kurz mit anbraten.")
        steps.append(f"{fluessigkeit} angießen, aufkochen, dann 15–20 Minuten bei milder Hitze köcheln lassen, bis alles gar ist." if fluessigkeit else "Mit Kokosmilch oder Brühe auffüllen und 15–20 Minuten köcheln lassen.")
        finish = join_de([x for x in [saeure, nuesse] if x])
        if staerke and finish:
            steps.append(f"Abschmecken, mit {finish} verfeinern und mit {staerke} servieren.")
        elif staerke:
            steps.append(f"Abschmecken und mit {staerke} servieren.")
        else:
            steps.append("Abschmecken und servieren.")
        return steps

    if kategorie == "Auflauf":
        steps = [f"Ofen auf 200°C Ober-/Unterhitze vorheizen.",
                 f"{gemuese} waschen, putzen und in Scheiben bzw. Stücke schneiden." if gemuese else "Alle Zutaten vorbereiten."]
        if staerke:
            steps.append(f"{staerke} vorbereiten bzw. vorkochen, falls nötig.")
        if huelsenfrucht:
            steps.append(f"{huelsenfrucht} unterheben.")
        steps.append("Alles in eine gefettete Auflaufform schichten.")
        if milchprodukt:
            steps.append(f"Mit {milchprodukt} bedecken.")
        if gewuerze:
            steps.append(f"Mit {gewuerze} würzen.")
        steps.append("Im Ofen 30–40 Minuten backen, bis die Oberfläche goldbraun ist und alles gar ist.")
        steps.append("Kurz ruhen lassen und servieren.")
        return steps

    if kategorie == "Pasta":
        steps = [f"{staerke} nach Packungsangabe in reichlich Salzwasser bissfest kochen, etwas Nudelwasser zurückbehalten." if staerke else "Glutenfreie Nudeln nach Packungsangabe kochen."]
        steps.append(f"{fett.capitalize()} in einer Pfanne erhitzen, {gemuese} darin andünsten." if gemuese else f"{fett.capitalize()} in einer Pfanne erhitzen.")
        if gewuerze:
            steps.append(f"{gewuerze} zugeben.")
        if fluessigkeit:
            steps.append(f"{fluessigkeit} angießen und kurz einköcheln lassen.")
        if milchprodukt:
            steps.append(f"{milchprodukt} unterrühren, bis eine cremige Sauce entsteht.")
        steps.append("Abgetropfte Nudeln zur Sauce geben, bei Bedarf etwas Nudelwasser unterrühren.")
        finish = join_de([x for x in [nuesse, saeure] if x])
        steps.append(f"Mit {finish} bestreuen, abschmecken und servieren." if finish else "Abschmecken und servieren.")
        return steps

    if kategorie == "Bowl":
        steps = [f"{staerke} nach Packungsangabe garen und etwas abkühlen lassen." if staerke else "Basis vorbereiten."]
        if huelsenfrucht:
            steps.append(f"{huelsenfrucht} vorbereiten bzw. erwärmen.")
        if gemuese:
            steps.append(f"{gemuese} waschen, putzen und klein schneiden bzw. kurz anbraten.")
        dressing_parts = join_de([x for x in [fett, saeure, gewuerze] if x])
        steps.append(f"Für das Dressing {dressing_parts} verrühren." if dressing_parts else "Ein Dressing nach Wahl anrühren.")
        steps.append("Alle Komponenten in einer Bowl anrichten und das Dressing darüber geben.")
        finish = join_de([x for x in [milchprodukt, nuesse] if x])
        steps.append(f"Mit {finish} toppen und servieren." if finish else "Servieren.")
        return steps

    if kategorie == "Frühstück":
        ei = join_de(names_by_role(zutaten, "Hülsenfrucht/Protein"))
        if staerke and fluessigkeit and not ei:
            # Porridge
            steps = [f"{staerke} mit {fluessigkeit} in einem Topf aufkochen und 5–8 Minuten köcheln lassen, bis eine cremige Konsistenz entsteht."]
            if gewuerze or suesse:
                steps.append(f"{join_de([x for x in [gewuerze, suesse] if x])} unterrühren.")
            finish = join_de([x for x in [gemuese, nuesse] if x])
            steps.append(f"Mit {finish} toppen und servieren." if finish else "Anrichten und servieren.")
            return steps
        if staerke and ei:
            # Pancakes/Waffeln
            steps = [f"{staerke}, {ei}{', ' + gewuerze if gewuerze else ''} und {fluessigkeit or 'etwas Flüssigkeit'} zu einem glatten Teig verrühren."]
            steps.append(f"{fett.capitalize()} in einer Pfanne erhitzen und den Teig portionsweise bei mittlerer Hitze von beiden Seiten goldbraun backen.")
            finish = join_de([x for x in [gemuese, suesse, nuesse] if x])
            steps.append(f"Mit {finish} servieren." if finish else "Servieren.")
            return steps
        if ei and not staerke:
            # Rührei/Scramble
            steps = [f"{gemuese} waschen, putzen und klein schneiden." if gemuese else "Zutaten vorbereiten.",
                     f"{fett.capitalize()} in einer Pfanne erhitzen, {gemuese} darin kurz andünsten." if gemuese else f"{fett.capitalize()} in einer Pfanne erhitzen."]
            steps.append(f"{ei} verquirlen bzw. zugeben und unter Rühren bei mittlerer Hitze stocken lassen.")
            finish = join_de([x for x in [milchprodukt, gewuerze] if x])
            steps.append(f"Mit {finish} würzen/verfeinern und sofort servieren." if finish else "Würzen und sofort servieren.")
            return steps
        # Smoothie Bowl / kalt angerührte Basis
        steps = ["Obst bei Bedarf schälen und grob zerkleinern." if gemuese else "Alle Zutaten abwiegen."]
        steps.append("Alle Zutaten in den Mixer geben und fein pürieren, bis eine dickflüssige, cremige Masse entsteht." if fluessigkeit else "Alle Zutaten im Mixer fein pürieren.")
        finish = join_de([x for x in [nuesse, milchprodukt, suesse] if x])
        steps.append(f"In eine Schale füllen, mit {finish} toppen und sofort servieren." if finish else "In eine Schale füllen und sofort servieren.")
        return steps

    if kategorie == "Snack":
        steps = [f"{gemuese} waschen, putzen und vorbereiten (schälen/schneiden je nach Rezept)." if gemuese else "Hauptzutat vorbereiten.",
                 f"Mit {join_de([x for x in [fett, gewuerze] if x])} vermengen." if (fett or gewuerze) else "Würzen."]
        steps.append("Im Ofen bei 200°C ca. 20–25 Minuten rösten/backen, bis alles knusprig/gar ist (alternativ in der Pfanne anbraten).")
        finish = join_de([x for x in [saeure, nuesse, milchprodukt] if x])
        steps.append(f"Mit {finish} servieren." if finish else "Servieren.")
        return steps

    if kategorie == "Dessert":
        steps = ["Alle Zutaten abwiegen und vorbereiten."]
        if huelsenfrucht or gemuese:
            base = join_de([x for x in [huelsenfrucht, gemuese] if x])
            steps.append(f"{base} fein pürieren bzw. verarbeiten.")
        if suesse or gewuerze:
            steps.append(f"{join_de([x for x in [suesse, gewuerze] if x])} unterrühren.")
        steps.append("Für mindestens 1–2 Stunden kalt stellen bzw. nach Rezept backen, bis die gewünschte Konsistenz erreicht ist.")
        finish = join_de([x for x in [nuesse, milchprodukt] if x])
        steps.append(f"Mit {finish} garnieren und servieren." if finish else "Garnieren und servieren.")
        return steps

    return ["Alle Zutaten vorbereiten.", "Nach Wunsch anbraten, kochen oder backen.", "Abschmecken und servieren."]

MACRO_RANGES = {
    "Frühstück": (320, 420, 8, 14, 10, 18, 40, 55, 6, 10),
    "Salat": (250, 380, 8, 16, 10, 20, 20, 35, 7, 12),
    "Suppe": (220, 320, 7, 13, 6, 14, 25, 40, 6, 10),
    "Bowl": (420, 560, 14, 22, 14, 22, 55, 70, 9, 14),
    "Pfannengericht": (380, 480, 12, 18, 14, 20, 40, 55, 8, 12),
    "Auflauf": (420, 550, 12, 20, 16, 26, 40, 55, 7, 11),
    "Curry": (380, 480, 10, 16, 16, 24, 40, 50, 8, 12),
    "Pasta": (480, 600, 14, 20, 14, 22, 65, 80, 6, 10),
    "Snack": (150, 280, 4, 10, 6, 16, 15, 30, 4, 8),
    "Dessert": (220, 380, 4, 10, 10, 22, 25, 40, 3, 7),
}

def estimate_macros(kategorie, name):
    r = random.Random(name)
    (kcal_lo, kcal_hi, p_lo, p_hi, f_lo, f_hi, kh_lo, kh_hi, b_lo, b_hi) = MACRO_RANGES[kategorie]
    return (r.randint(kcal_lo, kcal_hi), r.randint(p_lo, p_hi), r.randint(f_lo, f_hi),
            r.randint(kh_lo, kh_hi), r.randint(b_lo, b_hi))

def R(name, kategorie, kueche, geraete, zeit_aktiv, zeit_passiv, schwierigkeit, portionen, zutaten_tuples, kosten_kat, tags=None, thermomix=None):
    zutaten = [z(*t) for t in zutaten_tuples]
    zubereitung = build_steps(kategorie, zutaten, kueche)
    kcal, protein, fett, kh, ballaststoffe = estimate_macros(kategorie, name)
    add_recipe(name, kategorie, kueche, geraete, zeit_aktiv, zeit_passiv, schwierigkeit, portionen,
               zutaten, zubereitung, kosten_kat, kcal, protein, fett, kh, ballaststoffe, tags, thermomix)

G = "Gemüse"
HP = "Hülsenfrucht/Protein"
ST = "Getreide/Stärke"
FO = "Fett/Öl"
GW = "Gewürz/Kräuter"
FL = "Flüssigkeit"
ML = "Milchprodukt (laktosefrei)"
NU = "Nuss/Kern"
SA = "Säure/Topping"
SU = "Süße"

# ============================= FRÜHSTÜCK (20) =============================
R("Apfel-Zimt-Porridge mit Walnüssen", "Frühstück", "International", ["Herd"], 5, 8, "einfach", 2,
  [("glutenfreie Haferflocken",80,"g",ST), ("laktosefreie Milch",300,"ml",FL), ("Apfel",1,"Stück",G),
   ("Zimt",1,"TL",GW), ("Walnüsse",20,"g",NU), ("Ahornsirup",1,"EL",SU)],
  "günstig", ["schnell","mealprep-geeignet"], {"verfuegbar": True, "hinweis": "Hafer und Milch 6 Min/90°C/Stufe 2 kochen, restliche Zutaten unterrühren."})

R("Beeren-Porridge mit Mandelmus", "Frühstück", "International", ["Herd"], 5, 8, "einfach", 2,
  [("glutenfreie Haferflocken",80,"g",ST), ("Kokosmilch",300,"ml",FL), ("gemischte Beeren",100,"g",G),
   ("Mandelmus",20,"g",NU), ("Chiasamen",1,"EL",SU)],
  "mittel", ["schnell"], {"verfuegbar": True, "hinweis": "Hafer mit Kokosmilch 6 Min/90°C/Stufe 2 kochen."})

R("Bananen-Kakao-Porridge mit Kürbiskernen", "Frühstück", "International", ["Herd"], 5, 8, "einfach", 2,
  [("glutenfreie Haferflocken",80,"g",ST), ("laktosefreie Milch",300,"ml",FL), ("Banane",1,"Stück",G),
   ("Kakaopulver",1,"EL",GW), ("Kürbiskerne",20,"g",NU)],
  "günstig", ["schnell","kinderfreundlich"])

R("Birnen-Kardamom-Porridge mit Haselnüssen", "Frühstück", "International", ["Herd"], 5, 8, "einfach", 2,
  [("glutenfreie Haferflocken",80,"g",ST), ("Kokosmilch",300,"ml",FL), ("Birne",1,"Stück",G),
   ("Kardamom",0.5,"TL",GW), ("Haselnüsse",20,"g",NU)],
  "mittel", [])

R("Mango-Kokos-Porridge mit Chiasamen", "Frühstück", "Asiatisch", ["Herd"], 5, 8, "einfach", 2,
  [("glutenfreie Haferflocken",80,"g",ST), ("Kokosmilch",300,"ml",FL), ("Mango",0.5,"Stück",G),
   ("Kokosraspeln",15,"g",SU), ("Chiasamen",1,"EL",SU)],
  "mittel", ["mealprep-geeignet"])

R("Pflaumen-Porridge mit Pekannüssen", "Frühstück", "International", ["Herd"], 5, 8, "einfach", 2,
  [("glutenfreie Haferflocken",80,"g",ST), ("laktosefreie Milch",300,"ml",FL), ("Pflaumen",4,"Stück",G),
   ("Zimt",0.5,"TL",GW), ("Pekannüsse",20,"g",NU)],
  "mittel", [])

R("Buchweizen-Pancakes mit Beeren", "Frühstück", "International", ["Herd"], 15, 10, "mittel", 2,
  [("Buchweizenmehl",120,"g",ST), ("Ei",2,"Stück",HP), ("laktosefreie Milch",150,"ml",FL),
   ("Backpulver (glutenfrei)",1,"TL",GW), ("gemischte Beeren",100,"g",G), ("Ahornsirup",2,"EL",SU),
   ("Öl zum Braten",1,"EL",FO)],
  "günstig", ["kinderfreundlich"])

R("Vegane Bananen-Pancakes", "Frühstück", "International", ["Herd"], 15, 10, "mittel", 2,
  [("Reismehl",100,"g",ST), ("Banane",1,"Stück",G), ("Leinsamen geschrotet",1,"EL",HP),
   ("Backpulver (glutenfrei)",1,"TL",GW), ("Hafermilch",120,"ml",FL), ("Kokosöl",1,"EL",FO)],
  "günstig", ["vegan"])

R("Kürbis-Pancakes mit Zimt", "Frühstück", "International", ["Herd"], 15, 10, "mittel", 2,
  [("Reismehl",100,"g",ST), ("Kürbispüree",100,"g",G), ("Ei",1,"Stück",HP),
   ("Zimt",1,"TL",GW), ("laktosefreie Milch",80,"ml",FL), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Mandelmehl-Waffeln mit Ahornsirup", "Frühstück", "International", ["Herd"], 15, 10, "mittel", 2,
  [("Mandelmehl",100,"g",NU), ("Ei",2,"Stück",HP), ("Backpulver (glutenfrei)",1,"TL",GW),
   ("laktosefreie Milch",80,"ml",FL), ("Ahornsirup",2,"EL",SU)],
  "mittel", [])

R("Herzhafte Karotten-Pancakes", "Frühstück", "International", ["Herd"], 15, 10, "mittel", 2,
  [("Buchweizenmehl",100,"g",ST), ("Karotte geraspelt",1,"Stück",G), ("Ei",2,"Stück",HP),
   ("Petersilie",1,"EL",GW), ("Öl zum Braten",1,"EL",FO)],
  "günstig", [])

R("Gemüse-Rührei", "Frühstück", "International", ["Herd"], 10, 5, "einfach", 2,
  [("Ei",4,"Stück",HP), ("Paprika",0.5,"Stück",G), ("Zucchini",0.5,"Stück",G),
   ("Lauch",0.5,"Stange",G), ("Olivenöl",1,"EL",FO), ("Petersilie",1,"EL",GW)],
  "günstig", ["schnell"])

R("Kichererbsenmehl-Scramble vegan", "Frühstück", "International", ["Herd"], 10, 5, "einfach", 2,
  [("Kichererbsenmehl",80,"g",ST), ("Wasser",150,"ml",FL), ("Kurkuma",0.5,"TL",GW),
   ("Paprika",0.5,"Stück",G), ("Champignons",80,"g",G), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan"])

R("Pilz-Rührei mit Kräutern", "Frühstück", "International", ["Herd"], 10, 5, "einfach", 2,
  [("Ei",4,"Stück",HP), ("Champignons",100,"g",G), ("Schnittlauch",1,"EL",GW), ("Butter laktosefrei",1,"EL",FO)],
  "günstig", ["schnell"])

R("Spinat-Feta-Rührei", "Frühstück", "Mediterran", ["Herd"], 10, 5, "einfach", 2,
  [("Ei",4,"Stück",HP), ("Spinat",100,"g",G), ("Feta laktosefrei",50,"g",ML), ("Olivenöl",1,"EL",FO)],
  "mittel", ["schnell"])

R("Beeren-Smoothie-Bowl", "Frühstück", "International", ["Herd","Mixer/Pürierstab"], 10, 0, "einfach", 2,
  [("gefrorene Beeren",200,"g",G), ("Banane",1,"Stück",G), ("laktosefreier Joghurt",150,"g",ML),
   ("glutenfreies Granola",30,"g",ST)],
  "mittel", ["schnell","mealprep-geeignet"])

R("Grüne Smoothie-Bowl", "Frühstück", "International", ["Mixer/Pürierstab"], 10, 0, "einfach", 2,
  [("Spinat",50,"g",G), ("Banane",1,"Stück",G), ("Mango",0.5,"Stück",G), ("Kokosmilch",150,"ml",FL)],
  "mittel", ["vegan","schnell"])

R("Schoko-Bananen-Bowl mit Erdnussmus", "Frühstück", "International", ["Mixer/Pürierstab"], 10, 0, "einfach", 2,
  [("Banane",2,"Stück",G), ("Kakaopulver",1,"EL",GW), ("Erdnussmus",20,"g",NU), ("Hafermilch",100,"ml",FL)],
  "mittel", ["vegan"])

R("Drachenfrucht-Bowl", "Frühstück", "International", ["Mixer/Pürierstab"], 10, 0, "einfach", 2,
  [("Drachenfrucht gefroren",150,"g",G), ("Banane",1,"Stück",G), ("Kokosmilch",150,"ml",FL)],
  "hochwertig", ["vegan"])

R("Ananas-Kokos-Bowl mit Chiasamen", "Frühstück", "International", ["Mixer/Pürierstab"], 10, 0, "einfach", 2,
  [("Ananas",150,"g",G), ("Kokosmilch",150,"ml",FL), ("Kokosraspeln",15,"g",SU), ("Chiasamen",1,"EL",SU)],
  "mittel", ["vegan"])

# ============================== SALATE (20) ================================
R("Mediterraner Linsensalat", "Salat", "Mediterran", ["Herd"], 20, 0, "einfach", 2,
  [("braune Linsen",150,"g",HP), ("Paprika",1,"Stück",G), ("Tomate",2,"Stück",G),
   ("rote Zwiebel",0.5,"Stück",G), ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA), ("Oregano",1,"TL",GW)],
  "günstig", ["mealprep-geeignet","vegan"])

R("Quinoa-Tabouleh glutenfrei", "Salat", "Levantinisch", ["Herd"], 20, 0, "einfach", 2,
  [("Quinoa",150,"g",ST), ("Petersilie",30,"g",G), ("Minze",10,"g",GW), ("Tomate",2,"Stück",G),
   ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "mittel", ["vegan","mealprep-geeignet"])

R("Griechischer Salat mit laktosefreiem Feta", "Salat", "Mediterran", [], 15, 0, "einfach", 2,
  [("Gurke",1,"Stück",G), ("Tomate",2,"Stück",G), ("rote Zwiebel",0.5,"Stück",G),
   ("Oliven",50,"g",G), ("Feta laktosefrei",80,"g",ML), ("Olivenöl",2,"EL",FO), ("Oregano",1,"TL",GW)],
  "mittel", ["schnell"])

R("Rote-Bete-Salat mit laktosefreiem Frischkäse", "Salat", "International", ["Herd"], 15, 0, "einfach", 2,
  [("Rote Bete gekocht",250,"g",G), ("Walnüsse",20,"g",NU), ("Frischkäse laktosefrei",60,"g",ML),
   ("Olivenöl",1,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "mittel", [])

R("Karotten-Orangen-Salat mit Kreuzkümmel", "Salat", "Mediterran", [], 15, 0, "einfach", 2,
  [("Karotte",3,"Stück",G), ("Orange",1,"Stück",G), ("Kreuzkümmel",0.5,"TL",GW),
   ("Olivenöl",1,"EL",FO), ("Minze",5,"g",GW)],
  "günstig", ["vegan","schnell"])

R("Fenchel-Orangen-Salat", "Salat", "Mediterran", [], 15, 0, "einfach", 2,
  [("Fenchel",1,"Knolle",G), ("Orange",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Oliven",30,"g",G)],
  "günstig", ["vegan","schnell"])

R("Rucola-Birnen-Salat mit Walnüssen", "Salat", "Mediterran", [], 10, 0, "einfach", 2,
  [("Rucola",80,"g",G), ("Birne",1,"Stück",G), ("Walnüsse",25,"g",NU),
   ("Olivenöl",1,"EL",FO), ("Zitronensaft",1,"TL",SA)],
  "mittel", ["schnell"])

R("Thai-Glasnudelsalat mit Erdnüssen", "Salat", "Asiatisch", ["Herd"], 15, 0, "mittel", 2,
  [("Reisnudeln",120,"g",ST), ("Karotte",1,"Stück",G), ("Gurke",0.5,"Stück",G),
   ("Erdnüsse",20,"g",NU), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW), ("Sesamöl",1,"EL",FO)],
  "mittel", ["vegan"])

R("Mexikanischer Bohnensalat", "Salat", "Mexikanisch", [], 15, 0, "einfach", 2,
  [("schwarze Bohnen",200,"g",HP), ("Mais",100,"g",G), ("Paprika",0.5,"Stück",G),
   ("Avocado",1,"Stück",G), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Blumenkohl-Reis-Salat mit Granatapfel", "Salat", "Levantinisch", [], 15, 0, "einfach", 2,
  [("Blumenkohl",300,"g",G), ("Granatapfelkerne",50,"g",G), ("Petersilie",15,"g",GW),
   ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "mittel", ["vegan"])

R("Kichererbsen-Spinat-Salat mit Zitrone", "Salat", "Mediterran", [], 10, 0, "einfach", 2,
  [("Kichererbsen",250,"g",HP), ("Spinat",80,"g",G), ("Zitronensaft",1,"EL",SA), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Roter-Linsen-Salat Levantinisch mit Sumach", "Salat", "Levantinisch", ["Herd"], 20, 0, "einfach", 2,
  [("rote Linsen",150,"g",HP), ("Gurke",0.5,"Stück",G), ("Sumach",1,"TL",GW),
   ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "günstig", ["vegan"])

R("Gebackener Kürbis-Salat mit Kürbiskernen", "Salat", "International", ["Backofen"], 10, 25, "einfach", 2,
  [("Hokkaido-Kürbis",300,"g",G), ("Rucola",50,"g",G), ("Kürbiskerne",20,"g",NU),
   ("Olivenöl",2,"EL",FO), ("Ahornsirup",1,"EL",SU)],
  "mittel", ["vegan"])

R("Avocado-Mango-Salat", "Salat", "International", [], 10, 0, "einfach", 2,
  [("Avocado",1,"Stück",G), ("Mango",1,"Stück",G), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "mittel", ["vegan","schnell"])

R("Gurken-Dill-Salat mit Joghurt-Dressing", "Salat", "International", [], 10, 0, "einfach", 2,
  [("Gurke",1,"Stück",G), ("Dill",10,"g",GW), ("laktosefreier Joghurt",100,"g",ML), ("Zitronensaft",1,"TL",SA)],
  "günstig", ["schnell"])

R("Wintersalat Grünkohl-Granatapfel-Walnuss", "Salat", "International", [], 15, 0, "einfach", 2,
  [("Grünkohl",100,"g",G), ("Granatapfelkerne",50,"g",G), ("Walnüsse",25,"g",NU),
   ("Olivenöl",2,"EL",FO), ("Ahornsirup",1,"TL",SU)],
  "mittel", ["vegan"])

R("Süßkartoffel-Schwarzbohnen-Salat Mexikanisch", "Salat", "Mexikanisch", ["Backofen"], 10, 25, "einfach", 2,
  [("Süßkartoffel",300,"g",G), ("schwarze Bohnen",200,"g",HP), ("Limettensaft",1,"EL",SA),
   ("Koriander",10,"g",GW), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Rettich-Karotten-Salat mit Sesam-Dressing", "Salat", "Asiatisch", [], 15, 0, "einfach", 2,
  [("Rettich",150,"g",G), ("Karotte",2,"Stück",G), ("Sesam",1,"EL",NU),
   ("Reisessig",1,"EL",SA), ("Sesamöl",1,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Rosenkohl-Cranberry-Salat mit Pekannüssen", "Salat", "International", ["Herd"], 15, 0, "mittel", 2,
  [("Rosenkohl",250,"g",G), ("getrocknete Cranberries",30,"g",SU), ("Pekannüsse",25,"g",NU),
   ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "mittel", ["vegan"])

R("Tomaten-Melonen-Salat mit laktosefreiem Feta", "Salat", "Mediterran", [], 10, 0, "einfach", 2,
  [("Tomate",2,"Stück",G), ("Wassermelone",200,"g",G), ("Feta laktosefrei",60,"g",ML),
   ("Minze",10,"g",GW), ("Olivenöl",1,"EL",FO)],
  "mittel", ["schnell"])

# ============================== SUPPEN (20) =================================
R("Rote-Linsensuppe mit Kokosmilch & Curry", "Suppe", "Indisch", ["Herd"], 10, 20, "einfach", 2,
  [("rote Linsen",150,"g",HP), ("Zwiebel",1,"Stück",G), ("Knoblauch",2,"Zehen",G),
   ("Currypulver",1,"EL",GW), ("Kokosmilch",400,"ml",FL), ("Gemüsebrühe",300,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["mealprep-geeignet","vegan"],
  {"verfuegbar": True, "hinweis": "Zwiebel/Knoblauch zerkleinern (Stufe 7), andünsten (Varoma/3 Min), restliche Zutaten zugeben, 20 Min/100°C/Stufe 1 köcheln."})

R("Kürbiscremesuppe mit Ingwer", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 25, "einfach", 2,
  [("Hokkaido-Kürbis",400,"g",G), ("Zwiebel",1,"Stück",G), ("Ingwer",1,"Stück",GW),
   ("Gemüsebrühe",500,"ml",FL), ("Kokosmilch",100,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["mealprep-geeignet","vegan"])

R("Tomatensuppe Mediterran", "Suppe", "Mediterran", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("Tomaten",600,"g",G), ("Zwiebel",1,"Stück",G), ("Knoblauch",2,"Zehen",G),
   ("Basilikum",10,"g",GW), ("Gemüsebrühe",300,"ml",FL), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Blumenkohlsuppe mit Muskat", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("Blumenkohl",400,"g",G), ("Zwiebel",1,"Stück",G), ("Muskatnuss",1,"Prise",GW),
   ("Gemüsebrühe",400,"ml",FL), ("laktosefreie Sahne",80,"ml",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Brokkoli-Cremesuppe mit laktosefreiem Käse", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("Brokkoli",400,"g",G), ("Zwiebel",1,"Stück",G), ("laktosefreier Schmelzkäse",60,"g",ML),
   ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "mittel", [])

R("Süßkartoffel-Kokos-Suppe", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 25, "einfach", 2,
  [("Süßkartoffel",400,"g",G), ("Zwiebel",1,"Stück",G), ("Ingwer",1,"Stück",GW),
   ("Kokosmilch",300,"ml",FL), ("Gemüsebrühe",200,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Pastinaken-Apfel-Suppe", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 25, "einfach", 2,
  [("Pastinake",300,"g",G), ("Apfel",1,"Stück",G), ("Zwiebel",1,"Stück",G),
   ("Gemüsebrühe",500,"ml",FL), ("Butter laktosefrei",1,"EL",FO), ("Muskatnuss",1,"Prise",GW)],
  "mittel", [])

R("Zucchini-Minze-Suppe", "Suppe", "Mediterran", ["Herd","Mixer/Pürierstab"], 10, 15, "einfach", 2,
  [("Zucchini",400,"g",G), ("Zwiebel",1,"Stück",G), ("Minze",10,"g",GW),
   ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Rote-Bete-Suppe mit Joghurt-Topping", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 25, "einfach", 2,
  [("Rote Bete",400,"g",G), ("Zwiebel",1,"Stück",G), ("Gemüsebrühe",500,"ml",FL),
   ("laktosefreier Joghurt",60,"g",ML), ("Olivenöl",1,"EL",FO)],
  "mittel", [])

R("Erbsensuppe mit Minze", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 15, "einfach", 2,
  [("Erbsen (TK)",300,"g",G), ("Zwiebel",1,"Stück",G), ("Minze",10,"g",GW),
   ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Sellerie-Cremesuppe", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 25, "einfach", 2,
  [("Knollensellerie",350,"g",G), ("Zwiebel",1,"Stück",G), ("Gemüsebrühe",450,"ml",FL),
   ("laktosefreie Sahne",60,"ml",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Champignon-Cremesuppe mit Sahne", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("Champignons",300,"g",G), ("Zwiebel",1,"Stück",G), ("Thymian",1,"TL",GW),
   ("Gemüsebrühe",350,"ml",FL), ("laktosefreie Sahne",80,"ml",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Kichererbsen-Spinat-Eintopf", "Suppe", "Mediterran", ["Herd"], 10, 20, "einfach", 2,
  [("Kichererbsen",300,"g",HP), ("Spinat",100,"g",G), ("Tomaten gehackt",200,"g",G),
   ("Knoblauch",2,"Zehen",G), ("Kreuzkümmel",1,"TL",GW), ("Gemüsebrühe",300,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Schwarzbohnen-Suppe Mexikanisch", "Suppe", "Mexikanisch", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("schwarze Bohnen",300,"g",HP), ("Zwiebel",1,"Stück",G), ("Paprika",1,"Stück",G),
   ("Kreuzkümmel",1,"TL",GW), ("Limettensaft",1,"EL",SA), ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Karotten-Ingwer-Suppe", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("Karotte",400,"g",G), ("Ingwer",1,"Stück",GW), ("Zwiebel",1,"Stück",G),
   ("Gemüsebrühe",450,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Kokos-Gemüse-Suppe Thai-Style", "Suppe", "Asiatisch", ["Herd"], 15, 15, "einfach", 2,
  [("Kokosmilch",400,"ml",FL), ("Zitronengras",1,"Stange",GW), ("Paprika",1,"Stück",G),
   ("Pilze",100,"g",G), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "mittel", ["vegan"])

R("Weißkohl-Kartoffel-Eintopf", "Suppe", "Deutsch/Alpenländisch", ["Herd"], 15, 25, "einfach", 2,
  [("Weißkohl",300,"g",G), ("Kartoffel",300,"g",G), ("Zwiebel",1,"Stück",G),
   ("Kümmel",0.5,"TL",GW), ("Gemüsebrühe",500,"ml",FL), ("Butter laktosefrei",1,"EL",FO)],
  "günstig", ["mealprep-geeignet"])

R("Fenchel-Orangen-Suppe", "Suppe", "Mediterran", ["Herd","Mixer/Pürierstab"], 10, 20, "einfach", 2,
  [("Fenchel",2,"Knollen",G), ("Orange",1,"Stück",G), ("Zwiebel",1,"Stück",G),
   ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "mittel", ["vegan"])

R("Spargel-Cremesuppe", "Suppe", "International", ["Herd","Mixer/Pürierstab"], 10, 20, "mittel", 2,
  [("grüner Spargel",400,"g",G), ("Zwiebel",1,"Stück",G), ("Gemüsebrühe",400,"ml",FL),
   ("laktosefreie Sahne",80,"ml",ML), ("Butter laktosefrei",1,"EL",FO)],
  "hochwertig", [])

R("Minestrone glutenfrei", "Suppe", "Mediterran", ["Herd"], 15, 20, "einfach", 2,
  [("weiße Bohnen",200,"g",HP), ("Karotte",1,"Stück",G), ("Zucchini",1,"Stück",G),
   ("Tomaten gehackt",300,"g",G), ("Reisnudeln",60,"g",ST), ("Basilikum",10,"g",GW),
   ("Gemüsebrühe",500,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

# ================================ BOWLS (20) =================================
R("Buddha Bowl Mediterran", "Bowl", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Quinoa",150,"g",ST), ("Kichererbsen",200,"g",HP), ("Gurke",0.5,"Stück",G),
   ("Tomate",1,"Stück",G), ("Feta laktosefrei",60,"g",ML), ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "mittel", ["mealprep-geeignet"])

R("Burrito Bowl Mexikanisch", "Bowl", "Mexikanisch", ["Herd"], 15, 15, "einfach", 2,
  [("Reis",150,"g",ST), ("schwarze Bohnen",200,"g",HP), ("Mais",100,"g",G),
   ("Avocado",1,"Stück",G), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Poke-Style Bowl mit Sesam", "Bowl", "Asiatisch", ["Herd"], 15, 15, "mittel", 2,
  [("Reis",150,"g",ST), ("Avocado",1,"Stück",G), ("Gurke",0.5,"Stück",G),
   ("Rettich",50,"g",G), ("Sesam",1,"EL",NU), ("Sojasauce-Alternative (Kokosaminos)",1,"EL",SA), ("Sesamöl",1,"EL",FO)],
  "mittel", ["vegan"])

R("Falafel Bowl Levantinisch", "Bowl", "Levantinisch", ["Backofen","Herd"], 20, 20, "mittel", 2,
  [("Kichererbsen",250,"g",HP), ("Petersilie",20,"g",GW), ("Knoblauch",2,"Zehen",G),
   ("Kreuzkümmel",1,"TL",GW), ("Tahini",2,"EL",NU), ("Zitronensaft",1,"EL",SA), ("Hirse",120,"g",ST)],
  "mittel", ["vegan","mealprep-geeignet"])

R("Teriyaki-Gemüse-Bowl (ohne Soja)", "Bowl", "Asiatisch", ["Herd"], 15, 15, "einfach", 2,
  [("Reis",150,"g",ST), ("Brokkoli",150,"g",G), ("Karotte",1,"Stück",G),
   ("Kokosaminos",2,"EL",SA), ("Ingwer",1,"Stück",GW), ("Sesamöl",1,"EL",FO)],
  "günstig", ["vegan"])

R("Süßkartoffel-Schwarzbohnen-Bowl", "Bowl", "Mexikanisch", ["Backofen","Herd"], 10, 25, "einfach", 2,
  [("Süßkartoffel",300,"g",G), ("schwarze Bohnen",200,"g",HP), ("Avocado",1,"Stück",G),
   ("Limettensaft",1,"EL",SA), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Curry-Quinoa-Bowl Indisch", "Bowl", "Indisch", ["Herd"], 15, 15, "einfach", 2,
  [("Quinoa",150,"g",ST), ("Blumenkohl",150,"g",G), ("Kichererbsen",150,"g",HP),
   ("Currypulver",1,"EL",GW), ("Kokosmilch",150,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "mittel", ["vegan"])

R("Thai-Erdnuss-Bowl", "Bowl", "Asiatisch", ["Herd"], 15, 10, "mittel", 2,
  [("Reisnudeln",150,"g",ST), ("Karotte",1,"Stück",G), ("Erdnussmus",2,"EL",NU),
   ("Kokosaminos",1,"EL",SA), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "mittel", ["vegan"])

R("Herbst-Bowl Kürbis-Grünkohl-Walnuss", "Bowl", "International", ["Backofen","Herd"], 15, 25, "einfach", 2,
  [("Hokkaido-Kürbis",250,"g",G), ("Grünkohl",80,"g",G), ("Hirse",120,"g",ST),
   ("Walnüsse",25,"g",NU), ("Olivenöl",2,"EL",FO)],
  "mittel", ["vegan"])

R("Tex-Mex-Bowl mit Mais & Avocado", "Bowl", "Mexikanisch", ["Herd"], 15, 10, "einfach", 2,
  [("Reis",150,"g",ST), ("Mais",150,"g",G), ("Avocado",1,"Stück",G),
   ("Paprika",1,"Stück",G), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "günstig", ["vegan"])

R("Griechische Bowl mit Hirse & Feta", "Bowl", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Hirse",150,"g",ST), ("Gurke",0.5,"Stück",G), ("Tomate",1,"Stück",G),
   ("Feta laktosefrei",60,"g",ML), ("Oliven",30,"g",G), ("Olivenöl",2,"EL",FO)],
  "mittel", [])

R("Marokkanische Hirse-Bowl mit Granatapfel", "Bowl", "International", ["Herd"], 15, 15, "einfach", 2,
  [("Hirse",150,"g",ST), ("Kichererbsen",150,"g",HP), ("Granatapfelkerne",50,"g",G),
   ("Zimt",0.5,"TL",GW), ("Olivenöl",1,"EL",FO)],
  "mittel", ["vegan"])

R("Protein-Bowl mit Linsen & Rucola", "Bowl", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("braune Linsen",150,"g",HP), ("Rucola",50,"g",G), ("Tomate",1,"Stück",G),
   ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Kokos-Curry-Gemüse-Bowl", "Bowl", "Asiatisch", ["Herd"], 15, 15, "einfach", 2,
  [("Reis",150,"g",ST), ("Brokkoli",100,"g",G), ("Paprika",1,"Stück",G),
   ("Currypaste (fischsauce-frei)",1,"EL",GW), ("Kokosmilch",200,"ml",FL)],
  "mittel", ["vegan"])

R("Rote-Bete-Hummus-Bowl", "Bowl", "Levantinisch", ["Herd","Mixer/Pürierstab"], 15, 10, "einfach", 2,
  [("Rote Bete gekocht",150,"g",G), ("Kichererbsen",150,"g",HP), ("Tahini",1,"EL",NU),
   ("Hirse",120,"g",ST), ("Zitronensaft",1,"EL",SA)],
  "mittel", ["vegan"])

R("Buffalo-Blumenkohl-Bowl", "Bowl", "International", ["Backofen","Herd"], 15, 25, "mittel", 2,
  [("Blumenkohl",300,"g",G), ("Reis",150,"g",ST), ("Chilisauce",2,"EL",GW),
   ("laktosefreier Joghurt",80,"g",ML), ("Olivenöl",1,"EL",FO)],
  "mittel", [])

R("Reis-Bohnen-Bowl Kuba-Style", "Bowl", "International", ["Herd"], 15, 20, "einfach", 2,
  [("Reis",150,"g",ST), ("schwarze Bohnen",200,"g",HP), ("Paprika",1,"Stück",G),
   ("Kreuzkümmel",1,"TL",GW), ("Limettensaft",1,"EL",SA), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Pilz-Risotto-Bowl", "Bowl", "Mediterran", ["Herd"], 15, 25, "mittel", 2,
  [("Risotto-Reis",150,"g",ST), ("Champignons",200,"g",G), ("Gemüsebrühe",400,"ml",FL),
   ("laktosefreier Parmesan",30,"g",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Spinat-Quinoa-Bowl mit Pinienkernen", "Bowl", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Quinoa",150,"g",ST), ("Spinat",100,"g",G), ("Pinienkerne",20,"g",NU),
   ("Olivenöl",2,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "mittel", ["vegan"])

R("Kichererbsen-Sesam-Bowl", "Bowl", "Asiatisch", ["Herd"], 15, 15, "einfach", 2,
  [("Reis",150,"g",ST), ("Kichererbsen",200,"g",HP), ("Rettich",50,"g",G),
   ("Sesam",1,"EL",NU), ("Sesamöl",1,"EL",FO), ("Kokosaminos",1,"EL",SA)],
  "günstig", ["vegan"])

# ========================= PFANNENGERICHTE (25) =============================
R("Gemüse-Stir-Fry Asiatisch", "Pfannengericht", "Asiatisch", ["Herd"], 15, 10, "einfach", 2,
  [("Brokkoli",150,"g",G), ("Paprika",1,"Stück",G), ("Karotte",1,"Stück",G),
   ("Ingwer",1,"Stück",GW), ("Kokosaminos",2,"EL",SA), ("Sesamöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan","schnell"])

R("Kichererbsen-Curry-Pfanne", "Pfannengericht", "Indisch", ["Herd"], 15, 15, "einfach", 2,
  [("Kichererbsen",250,"g",HP), ("Tomaten gehackt",200,"g",G), ("Zwiebel",1,"Stück",G),
   ("Currypulver",1,"EL",GW), ("Kokosmilch",150,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Paprika-Zucchini-Pfanne Mediterran", "Pfannengericht", "Mediterran", ["Herd"], 15, 10, "einfach", 2,
  [("Paprika",2,"Stück",G), ("Zucchini",1,"Stück",G), ("Knoblauch",2,"Zehen",G),
   ("Oregano",1,"TL",GW), ("Olivenöl",2,"EL",FO), ("Feta laktosefrei",60,"g",ML)],
  "günstig", ["schnell"])

R("Süßkartoffel-Black-Bean-Pfanne Mexikanisch", "Pfannengericht", "Mexikanisch", ["Herd"], 15, 15, "einfach", 2,
  [("Süßkartoffel",300,"g",G), ("schwarze Bohnen",200,"g",HP), ("Paprika",1,"Stück",G),
   ("Kreuzkümmel",1,"TL",GW), ("Olivenöl",1,"EL",FO), ("Limettensaft",1,"EL",SA)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Pilz-Spinat-Pfanne mit Knoblauch", "Pfannengericht", "Mediterran", ["Herd"], 10, 10, "einfach", 2,
  [("Champignons",250,"g",G), ("Spinat",100,"g",G), ("Knoblauch",2,"Zehen",G),
   ("Butter laktosefrei",1,"EL",FO), ("Petersilie",1,"EL",GW)],
  "günstig", ["schnell"])

R("Brokkoli-Cashew-Pfanne Asiatisch", "Pfannengericht", "Asiatisch", ["Herd"], 15, 10, "einfach", 2,
  [("Brokkoli",250,"g",G), ("Cashewkerne",30,"g",NU), ("Knoblauch",2,"Zehen",G),
   ("Kokosaminos",2,"EL",SA), ("Sesamöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Blumenkohl-Curry-Pfanne Indisch", "Pfannengericht", "Indisch", ["Herd"], 15, 15, "einfach", 2,
  [("Blumenkohl",300,"g",G), ("Erbsen (TK)",100,"g",G), ("Currypulver",1,"EL",GW),
   ("Tomaten gehackt",150,"g",G), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

R("Linsen-Gemüse-Bolognese-Pfanne", "Pfannengericht", "Mediterran", ["Herd"], 15, 20, "einfach", 2,
  [("braune Linsen",150,"g",HP), ("Karotte",1,"Stück",G), ("Sellerie",1,"Stange",G),
   ("Tomaten gehackt",400,"g",G), ("Oregano",1,"TL",GW), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Ratatouille-Pfanne", "Pfannengericht", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Aubergine",1,"Stück",G), ("Zucchini",1,"Stück",G), ("Paprika",1,"Stück",G),
   ("Tomaten gehackt",200,"g",G), ("Thymian",1,"TL",GW), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan"])

R("Rosenkohl-Maronen-Pfanne", "Pfannengericht", "Deutsch/Alpenländisch", ["Herd"], 15, 15, "mittel", 2,
  [("Rosenkohl",300,"g",G), ("Maronen gegart",100,"g",G), ("Butter laktosefrei",1,"EL",FO),
   ("Ahornsirup",1,"EL",SU), ("Thymian",1,"TL",GW)],
  "mittel", [])

R("Grünkohl-Kichererbsen-Pfanne", "Pfannengericht", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Grünkohl",150,"g",G), ("Kichererbsen",200,"g",HP), ("Knoblauch",2,"Zehen",G),
   ("Chiliflocken",0.5,"TL",GW), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan"])

R("Paella-Style-Pfanne", "Pfannengericht", "Mediterran", ["Herd"], 15, 25, "mittel", 2,
  [("Reis",200,"g",ST), ("Paprika",1,"Stück",G), ("Erbsen (TK)",100,"g",G),
   ("Safran",1,"Prise",GW), ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",2,"EL",FO)],
  "hochwertig", ["vegan"])

R("Gebratener Reis Asiatisch mit Ei & Gemüse", "Pfannengericht", "Asiatisch", ["Herd"], 15, 10, "einfach", 2,
  [("Reis (gekocht, kalt)",300,"g",ST), ("Ei",2,"Stück",HP), ("Karotte",1,"Stück",G),
   ("Erbsen (TK)",80,"g",G), ("Kokosaminos",2,"EL",SA), ("Sesamöl",1,"EL",FO)],
  "günstig", ["schnell","mealprep-geeignet"])

R("Szechuan-Gemüsepfanne scharf", "Pfannengericht", "Asiatisch", ["Herd"], 15, 10, "mittel", 2,
  [("Paprika",1,"Stück",G), ("Brokkoli",150,"g",G), ("Chiliflocken",1,"TL",GW),
   ("Knoblauch",2,"Zehen",G), ("Kokosaminos",2,"EL",SA), ("Sesamöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

R("Honig-Senf-Karotten-Pfanne", "Pfannengericht", "International", ["Herd"], 10, 10, "einfach", 2,
  [("Karotte",400,"g",G), ("Senf",1,"EL",GW), ("Honig",1,"EL",SU), ("Butter laktosefrei",1,"EL",FO)],
  "günstig", ["schnell"])

R("Kartoffel-Spinat-Pfanne mit Kreuzkümmel", "Pfannengericht", "Indisch", ["Herd"], 15, 20, "einfach", 2,
  [("Kartoffel",400,"g",G), ("Spinat",150,"g",G), ("Kreuzkümmel",1,"TL",GW),
   ("Kurkuma",0.5,"TL",GW), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Fenchel-Orangen-Pfanne Mediterran", "Pfannengericht", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Fenchel",2,"Knollen",G), ("Orange",1,"Stück",G), ("Olivenöl",2,"EL",FO), ("Oliven",30,"g",G)],
  "mittel", ["vegan"])

R("Zoodles-Pfanne mit Pesto", "Pfannengericht", "Mediterran", ["Herd"], 15, 10, "einfach", 2,
  [("Zucchini (als Zoodles)",2,"Stück",G), ("Basilikum",30,"g",GW), ("Pinienkerne",20,"g",NU),
   ("laktosefreier Parmesan",30,"g",ML), ("Olivenöl",3,"EL",FO)],
  "mittel", ["schnell"])

R("Süß-Sauer-Gemüsepfanne Asiatisch", "Pfannengericht", "Asiatisch", ["Herd"], 15, 10, "einfach", 2,
  [("Paprika",1,"Stück",G), ("Ananas",150,"g",G), ("Karotte",1,"Stück",G),
   ("Reisessig",2,"EL",SA), ("Ahornsirup",1,"EL",SU), ("Sesamöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

R("Kürbis-Salbei-Pfanne mit laktosefreier Butter", "Pfannengericht", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Hokkaido-Kürbis",350,"g",G), ("Salbei",10,"g",GW), ("Butter laktosefrei",2,"EL",FO),
   ("Walnüsse",20,"g",NU)],
  "mittel", [])

R("Erbsen-Minze-Pfanne mit Kartoffeln", "Pfannengericht", "International", ["Herd"], 15, 15, "einfach", 2,
  [("Erbsen (TK)",200,"g",G), ("Kartoffel",300,"g",G), ("Minze",10,"g",GW), ("Butter laktosefrei",1,"EL",FO)],
  "günstig", ["schnell"])

R("Auberginen-Granatapfel-Pfanne Levantinisch", "Pfannengericht", "Levantinisch", ["Herd"], 15, 15, "einfach", 2,
  [("Aubergine",2,"Stück",G), ("Granatapfelkerne",50,"g",G), ("Tahini",1,"EL",NU),
   ("Olivenöl",2,"EL",FO), ("Petersilie",10,"g",GW)],
  "mittel", ["vegan"])

R("Schwarzbohnen-Mais-Pfanne Tex-Mex", "Pfannengericht", "Mexikanisch", ["Herd"], 10, 10, "einfach", 2,
  [("schwarze Bohnen",250,"g",HP), ("Mais",150,"g",G), ("Paprika",1,"Stück",G),
   ("Kreuzkümmel",1,"TL",GW), ("Olivenöl",1,"EL",FO), ("Limettensaft",1,"EL",SA)],
  "günstig", ["vegan","schnell"])

R("Pilz-Risotto-Pfanne cremig", "Pfannengericht", "Mediterran", ["Herd"], 15, 25, "mittel", 2,
  [("Risotto-Reis",180,"g",ST), ("Champignons",250,"g",G), ("Gemüsebrühe",450,"ml",FL),
   ("laktosefreie Sahne",80,"ml",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Gemüse-Thai-Rot-Curry-Pfanne", "Pfannengericht", "Asiatisch", ["Herd"], 15, 15, "einfach", 2,
  [("Paprika",1,"Stück",G), ("Brokkoli",150,"g",G), ("Currypaste rot (fischsauce-frei)",1,"EL",GW),
   ("Kokosmilch",200,"ml",FL), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

# ============================ AUFLÄUFE/OFEN (25) ==============================
R("Kartoffel-Gratin laktosefrei", "Auflauf", "Deutsch/Alpenländisch", ["Backofen"], 20, 40, "mittel", 4,
  [("Kartoffel",800,"g",G), ("laktosefreie Sahne",300,"ml",ML), ("Knoblauch",2,"Zehen",G),
   ("Muskatnuss",1,"Prise",GW), ("laktosefreier Hartkäse",80,"g",ML)],
  "mittel", ["mealprep-geeignet"])

R("Gemüse-Lasagne glutenfrei", "Auflauf", "Mediterran", ["Backofen","Herd"], 25, 35, "mittel", 4,
  [("glutenfreie Lasagneplatten",250,"g",ST), ("Zucchini",2,"Stück",G), ("Aubergine",1,"Stück",G),
   ("Tomaten gehackt",500,"g",G), ("laktosefreie Sahne",200,"ml",ML), ("laktosefreier Hartkäse",80,"g",ML), ("Basilikum",10,"g",GW)],
  "mittel", ["mealprep-geeignet"])

R("Ofengemüse Mediterran", "Auflauf", "Mediterran", ["Backofen"], 15, 30, "einfach", 2,
  [("Paprika",2,"Stück",G), ("Zucchini",1,"Stück",G), ("rote Zwiebel",1,"Stück",G),
   ("Kirschtomaten",200,"g",G), ("Olivenöl",3,"EL",FO), ("Oregano",1,"TL",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Blumenkohl-Käse-Auflauf laktosefrei", "Auflauf", "International", ["Backofen","Herd"], 15, 30, "einfach", 2,
  [("Blumenkohl",500,"g",G), ("laktosefreie Sahne",200,"ml",ML), ("laktosefreier Hartkäse",80,"g",ML),
   ("Muskatnuss",1,"Prise",GW)],
  "mittel", [])

R("Süßkartoffel-Auflauf mit Pekannüssen", "Auflauf", "International", ["Backofen"], 15, 35, "einfach", 2,
  [("Süßkartoffel",500,"g",G), ("Pekannüsse",30,"g",NU), ("Ahornsirup",2,"EL",SU),
   ("Zimt",1,"TL",GW), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", ["vegan"])

R("Moussaka vegetarisch glutenfrei", "Auflauf", "Mediterran", ["Backofen","Herd"], 25, 40, "schwer", 4,
  [("Aubergine",2,"Stück",G), ("braune Linsen",200,"g",HP), ("Tomaten gehackt",300,"g",G),
   ("laktosefreie Milch",300,"ml",ML), ("Zimt",0.5,"TL",GW), ("Olivenöl",2,"EL",FO)],
  "mittel", ["mealprep-geeignet"])

R("Ofenkürbis mit Feta & Granatapfel", "Auflauf", "Mediterran", ["Backofen"], 10, 30, "einfach", 2,
  [("Hokkaido-Kürbis",400,"g",G), ("Feta laktosefrei",80,"g",ML), ("Granatapfelkerne",50,"g",G),
   ("Olivenöl",2,"EL",FO), ("Thymian",1,"TL",GW)],
  "mittel", [])

R("Gebackene Süßkartoffel gefüllt mit Bohnen", "Auflauf", "Mexikanisch", ["Backofen"], 10, 40, "einfach", 2,
  [("Süßkartoffel",2,"Stück",G), ("schwarze Bohnen",200,"g",HP), ("Avocado",1,"Stück",G),
   ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Ofen-Falafel-Teller", "Auflauf", "Levantinisch", ["Backofen"], 20, 25, "mittel", 2,
  [("Kichererbsen",250,"g",HP), ("Petersilie",20,"g",GW), ("Knoblauch",2,"Zehen",G),
   ("Kreuzkümmel",1,"TL",GW), ("Tahini",2,"EL",NU), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan"])

R("Rosenkohl-Auflauf mit laktosefreier Sahne", "Auflauf", "Deutsch/Alpenländisch", ["Backofen"], 15, 30, "einfach", 2,
  [("Rosenkohl",400,"g",G), ("laktosefreie Sahne",200,"ml",ML), ("laktosefreier Hartkäse",60,"g",ML),
   ("Muskatnuss",1,"Prise",GW)],
  "mittel", [])

R("Gemüse-Quiche glutenfrei (Mandelmehlboden)", "Auflauf", "Mediterran", ["Backofen"], 25, 35, "mittel", 4,
  [("Mandelmehl",150,"g",NU), ("Ei",4,"Stück",HP), ("Spinat",150,"g",G),
   ("laktosefreie Sahne",150,"ml",ML), ("Butter laktosefrei",50,"g",FO)],
  "mittel", ["mealprep-geeignet"])

R("Ofen-Risotto mit Pilzen", "Auflauf", "Mediterran", ["Backofen","Herd"], 15, 35, "mittel", 2,
  [("Risotto-Reis",180,"g",ST), ("Champignons",250,"g",G), ("Gemüsebrühe",450,"ml",FL),
   ("laktosefreier Parmesan",40,"g",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Polenta-Auflauf mit Tomaten & Käse", "Auflauf", "Mediterran", ["Backofen","Herd"], 20, 25, "einfach", 2,
  [("Polenta/Maisgrieß",150,"g",ST), ("Tomaten gehackt",300,"g",G), ("laktosefreier Hartkäse",60,"g",ML),
   ("Basilikum",10,"g",GW), ("Olivenöl",2,"EL",FO)],
  "günstig", [])

R("Shepherd's Pie vegetarisch", "Auflauf", "International", ["Backofen","Herd"], 25, 35, "mittel", 4,
  [("braune Linsen",250,"g",HP), ("Karotte",2,"Stück",G), ("Erbsen (TK)",150,"g",G),
   ("Kartoffel",700,"g",G), ("Butter laktosefrei",2,"EL",FO), ("Thymian",1,"TL",GW)],
  "günstig", ["mealprep-geeignet"])

R("Ofengemüse Marokkanisch mit Harissa", "Auflauf", "International", ["Backofen"], 15, 30, "einfach", 2,
  [("Süßkartoffel",300,"g",G), ("Kichererbsen",200,"g",HP), ("Harissa",1,"EL",GW),
   ("Olivenöl",2,"EL",FO), ("Koriander",10,"g",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Gefüllte Paprika mit Quinoa & Kichererbsen", "Auflauf", "Mediterran", ["Backofen"], 20, 30, "einfach", 2,
  [("Paprika",4,"Stück",G), ("Quinoa",150,"g",ST), ("Kichererbsen",150,"g",HP),
   ("Tomaten gehackt",150,"g",G), ("Oregano",1,"TL",GW), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan"])

R("Gefüllte Zucchini mit Reis & Gemüse", "Auflauf", "Mediterran", ["Backofen"], 20, 30, "einfach", 2,
  [("Zucchini",2,"Stück",G), ("Reis",100,"g",ST), ("Tomate",1,"Stück",G),
   ("Knoblauch",1,"Zehe",G), ("Olivenöl",1,"EL",FO), ("laktosefreier Hartkäse",40,"g",ML)],
  "günstig", [])

R("Auberginen-Parmigiana laktosefrei", "Auflauf", "Mediterran", ["Backofen","Herd"], 25, 35, "mittel", 4,
  [("Aubergine",2,"Stück",G), ("Tomaten gehackt",400,"g",G), ("laktosefreier Mozzarella",150,"g",ML),
   ("Basilikum",15,"g",GW), ("Olivenöl",3,"EL",FO)],
  "mittel", ["mealprep-geeignet"])

R("Kürbis-Gnocchi-Auflauf", "Auflauf", "Mediterran", ["Backofen","Herd"], 15, 25, "einfach", 2,
  [("glutenfreie Gnocchi",400,"g",ST), ("Hokkaido-Kürbis",200,"g",G), ("Salbei",10,"g",GW),
   ("laktosefreie Sahne",150,"ml",ML), ("Butter laktosefrei",1,"EL",FO)],
  "mittel", [])

R("Wurzelgemüse-Auflauf mit Rosmarin", "Auflauf", "Deutsch/Alpenländisch", ["Backofen"], 15, 35, "einfach", 2,
  [("Karotte",2,"Stück",G), ("Pastinake",2,"Stück",G), ("Kartoffel",2,"Stück",G),
   ("Rosmarin",1,"TL",GW), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Reisnudel-Auflauf Asiatisch", "Auflauf", "Asiatisch", ["Backofen","Herd"], 15, 25, "einfach", 2,
  [("Reisnudeln",200,"g",ST), ("Karotte",1,"Stück",G), ("Brokkoli",100,"g",G),
   ("Kokosaminos",2,"EL",SA), ("Sesamöl",1,"EL",FO)],
  "günstig", ["vegan"])

R("Brokkoli-Reis-Auflauf cremig", "Auflauf", "International", ["Backofen","Herd"], 15, 30, "einfach", 2,
  [("Reis",150,"g",ST), ("Brokkoli",250,"g",G), ("laktosefreie Sahne",150,"ml",ML),
   ("laktosefreier Hartkäse",60,"g",ML)],
  "mittel", [])

R("Kichererbsen-Spinat-Auflauf Indisch", "Auflauf", "Indisch", ["Backofen","Herd"], 15, 25, "einfach", 2,
  [("Kichererbsen",250,"g",HP), ("Spinat",150,"g",G), ("Kokosmilch",150,"ml",FL),
   ("Currypulver",1,"EL",GW), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Pilz-Walnuss-Bratling im Ofen", "Auflauf", "International", ["Backofen"], 20, 25, "mittel", 2,
  [("Champignons",250,"g",G), ("Walnüsse",50,"g",NU), ("Ei",1,"Stück",HP),
   ("Petersilie",10,"g",GW), ("Reismehl",30,"g",ST)],
  "mittel", [])

R("Süßkartoffel-Schwarzbohnen-Enchiladas", "Auflauf", "Mexikanisch", ["Backofen","Herd"], 20, 25, "mittel", 2,
  [("Mais-Tortillas (glutenfrei)",6,"Stück",ST), ("Süßkartoffel",250,"g",G), ("schwarze Bohnen",200,"g",HP),
   ("Tomatensauce",300,"ml",G), ("laktosefreier Hartkäse",60,"g",ML), ("Koriander",10,"g",GW)],
  "mittel", ["mealprep-geeignet"])

# ================================ CURRYS (20) =================================
R("Rotes Thai-Gemüsecurry", "Curry", "Asiatisch", ["Herd"], 15, 20, "einfach", 2,
  [("Currypaste rot (fischsauce-frei)",2,"EL",GW), ("Kokosmilch",400,"ml",FL), ("Paprika",1,"Stück",G),
   ("Brokkoli",150,"g",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Grünes Thai-Gemüsecurry", "Curry", "Asiatisch", ["Herd"], 15, 20, "einfach", 2,
  [("Currypaste grün (fischsauce-frei)",2,"EL",GW), ("Kokosmilch",400,"ml",FL), ("Zucchini",1,"Stück",G),
   ("grüne Bohnen",150,"g",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Gelbes Curry mit Kartoffeln", "Curry", "Asiatisch", ["Herd"], 15, 25, "einfach", 2,
  [("Currypulver gelb",1,"EL",GW), ("Kokosmilch",400,"ml",FL), ("Kartoffel",300,"g",G),
   ("Karotte",1,"Stück",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Chana Masala (Kichererbsen-Curry)", "Curry", "Indisch", ["Herd"], 15, 20, "einfach", 2,
  [("Kichererbsen",300,"g",HP), ("Tomaten gehackt",300,"g",G), ("Zwiebel",1,"Stück",G),
   ("Ingwer",1,"Stück",GW), ("Garam Masala",1,"EL",GW), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Rote-Linsen-Dal", "Curry", "Indisch", ["Herd"], 10, 20, "einfach", 2,
  [("rote Linsen",200,"g",HP), ("Zwiebel",1,"Stück",G), ("Knoblauch",2,"Zehen",G),
   ("Kurkuma",1,"TL",GW), ("Kreuzkümmel",1,"TL",GW), ("Gemüsebrühe",400,"ml",FL), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"],
  {"verfuegbar": True, "hinweis": "Zwiebel/Knoblauch 3 Sek/Stufe 5 zerkleinern, andünsten, Linsen & Brühe zugeben, 20 Min/100°C/Stufe 1."})

R("Kürbis-Kokos-Curry", "Curry", "Asiatisch", ["Herd"], 15, 20, "einfach", 2,
  [("Hokkaido-Kürbis",350,"g",G), ("Kokosmilch",350,"ml",FL), ("Currypaste rot (fischsauce-frei)",1,"EL",GW),
   ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Aloo Gobi (Blumenkohl-Erbsen-Curry)", "Curry", "Indisch", ["Herd"], 15, 20, "einfach", 2,
  [("Blumenkohl",300,"g",G), ("Kartoffel",200,"g",G), ("Erbsen (TK)",100,"g",G),
   ("Kurkuma",1,"TL",GW), ("Kreuzkümmel",1,"TL",GW), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

R("Auberginen-Curry", "Curry", "Indisch", ["Herd"], 15, 20, "einfach", 2,
  [("Aubergine",2,"Stück",G), ("Tomaten gehackt",300,"g",G), ("Zwiebel",1,"Stück",G),
   ("Garam Masala",1,"EL",GW), ("Olivenöl",1,"EL",FO), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

R("Süßkartoffel-Erdnuss-Curry Afrikanisch", "Curry", "International", ["Herd"], 15, 20, "einfach", 2,
  [("Süßkartoffel",300,"g",G), ("Erdnussmus",2,"EL",NU), ("Tomaten gehackt",200,"g",G),
   ("Zwiebel",1,"Stück",G), ("Ingwer",1,"Stück",GW), ("Olivenöl",1,"EL",FO), ("Gemüsebrühe",300,"ml",FL), ("Reis",150,"g",ST)],
  "mittel", ["vegan","mealprep-geeignet"])

R("Massaman-Gemüse-Curry", "Curry", "Asiatisch", ["Herd"], 15, 25, "mittel", 2,
  [("Kartoffel",250,"g",G), ("Karotte",1,"Stück",G), ("Zwiebel",1,"Stück",G),
   ("Currypaste Massaman (fischsauce-frei)",1,"EL",GW), ("Olivenöl",1,"EL",FO),
   ("Kokosmilch",400,"ml",FL), ("Erdnüsse",20,"g",NU), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Panang-Gemüse-Curry", "Curry", "Asiatisch", ["Herd"], 15, 20, "mittel", 2,
  [("Paprika",1,"Stück",G), ("Zwiebel",1,"Stück",G), ("Currypaste Panang (fischsauce-frei)",1,"EL",GW),
   ("Olivenöl",1,"EL",FO), ("Kokosmilch",350,"ml",FL), ("Erdnussmus",1,"EL",NU), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Kichererbsen-Kokos-Curry", "Curry", "Indisch", ["Herd"], 15, 20, "einfach", 2,
  [("Kichererbsen",300,"g",HP), ("Spinat",100,"g",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO),
   ("Kokosmilch",300,"ml",FL), ("Currypulver",1,"EL",GW), ("Reis",150,"g",ST)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Spinat-Kokos-Curry", "Curry", "Indisch", ["Herd"], 10, 15, "einfach", 2,
  [("Spinat",300,"g",G), ("Olivenöl",1,"EL",FO), ("Kokosmilch",300,"ml",FL), ("Ingwer",1,"Stück",GW),
   ("Kurkuma",1,"TL",GW), ("Reis",150,"g",ST)],
  "günstig", ["vegan","schnell"])

R("Pilz-Curry Cremig", "Curry", "Indisch", ["Herd"], 15, 15, "einfach", 2,
  [("Champignons",300,"g",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("laktosefreie Sahne",150,"ml",ML),
   ("Garam Masala",1,"EL",GW), ("Reis",150,"g",ST)],
  "mittel", [])

R("Karibisches Bohnen-Curry", "Curry", "International", ["Herd"], 15, 20, "einfach", 2,
  [("Kidneybohnen",300,"g",HP), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Kokosmilch",300,"ml",FL),
   ("Paprika",1,"Stück",G), ("Thymian",1,"TL",GW), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

R("Rote-Bete-Curry", "Curry", "Indisch", ["Herd"], 15, 25, "einfach", 2,
  [("Rote Bete",350,"g",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO), ("Kokosmilch",300,"ml",FL),
   ("Currypulver",1,"EL",GW), ("Ingwer",1,"Stück",GW), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Grünkohl-Kichererbsen-Curry", "Curry", "International", ["Herd"], 15, 20, "einfach", 2,
  [("Grünkohl",150,"g",G), ("Kichererbsen",250,"g",HP), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO),
   ("Tomaten gehackt",200,"g",G), ("Kreuzkümmel",1,"TL",GW), ("Reis",150,"g",ST)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Butter-Kichererbsen-Curry (vegetarisch)", "Curry", "Indisch", ["Herd"], 15, 20, "einfach", 2,
  [("Kichererbsen",300,"g",HP), ("Tomaten gehackt",300,"g",G), ("laktosefreie Sahne",150,"ml",ML),
   ("Garam Masala",1,"EL",GW), ("Butter laktosefrei",1,"EL",FO), ("Reis",150,"g",ST)],
  "mittel", [])

R("Jackfruit-Curry", "Curry", "Asiatisch", ["Herd"], 15, 20, "mittel", 2,
  [("Jackfruit (jung, aus der Dose)",300,"g",HP), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO),
   ("Kokosmilch",300,"ml",FL), ("Currypaste rot (fischsauce-frei)",1,"EL",GW), ("Reis",150,"g",ST)],
  "mittel", ["vegan"])

R("Rotkohl-Apfel-Curry", "Curry", "International", ["Herd"], 15, 20, "einfach", 2,
  [("Rotkohl",300,"g",G), ("Apfel",1,"Stück",G), ("Zwiebel",1,"Stück",G), ("Olivenöl",1,"EL",FO),
   ("Currypulver",1,"EL",GW), ("Kokosmilch",250,"ml",FL), ("Reis",150,"g",ST)],
  "günstig", ["vegan"])

# =========================== PASTA glutenfrei (20) ============================
R("Tomaten-Basilikum-Pasta", "Pasta", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Tomaten gehackt",400,"g",G), ("Knoblauch",2,"Zehen",G),
   ("Basilikum",15,"g",GW), ("Olivenöl",3,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Pasta Aglio e Olio glutenfrei", "Pasta", "Mediterran", ["Herd"], 5, 10, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Knoblauch",4,"Zehen",G), ("Chiliflocken",0.5,"TL",GW),
   ("Olivenöl",4,"EL",FO), ("Petersilie",10,"g",GW)],
  "günstig", ["vegan","schnell"])

R("Pasta mit Pilzrahmsauce", "Pasta", "International", ["Herd"], 10, 15, "einfach", 2,
  [("Maisnudeln",200,"g",ST), ("Champignons",250,"g",G), ("laktosefreie Sahne",150,"ml",ML),
   ("Knoblauch",1,"Zehe",G), ("Petersilie",10,"g",GW)],
  "mittel", [])

R("Pasta Puttanesca vegetarisch", "Pasta", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Linsennudeln",200,"g",ST), ("Tomaten gehackt",350,"g",G), ("Oliven",50,"g",G),
   ("Kapern",1,"EL",SA), ("Knoblauch",2,"Zehen",G), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan"])

R("Pasta mit Rucola-Pesto & Pinienkernen", "Pasta", "Mediterran", ["Herd","Mixer/Pürierstab"], 10, 10, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Rucola",60,"g",G), ("Pinienkerne",25,"g",NU),
   ("laktosefreier Parmesan",30,"g",ML), ("Olivenöl",4,"EL",FO)],
  "mittel", ["schnell"])

R("Linsennudel-Bolognese", "Pasta", "Mediterran", ["Herd"], 15, 20, "einfach", 2,
  [("Linsennudeln",200,"g",ST), ("braune Linsen",100,"g",HP), ("Karotte",1,"Stück",G),
   ("Tomaten gehackt",400,"g",G), ("Oregano",1,"TL",GW), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Kürbis-Salbei-Pasta mit laktosefreier Butter", "Pasta", "Mediterran", ["Herd"], 15, 20, "einfach", 2,
  [("Maisnudeln",200,"g",ST), ("Hokkaido-Kürbis",250,"g",G), ("Salbei",10,"g",GW),
   ("Butter laktosefrei",2,"EL",FO), ("laktosefreier Parmesan",30,"g",ML)],
  "mittel", [])

R("Zitronen-Spargel-Pasta", "Pasta", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("grüner Spargel",250,"g",G), ("Zitronensaft",1,"EL",SA),
   ("Olivenöl",3,"EL",FO), ("laktosefreier Parmesan",30,"g",ML)],
  "mittel", [])

R("Pasta Primavera", "Pasta", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Zucchini",1,"Stück",G), ("Erbsen (TK)",100,"g",G),
   ("Karotte",1,"Stück",G), ("Olivenöl",3,"EL",FO), ("Basilikum",10,"g",GW)],
  "günstig", ["vegan"])

R("Avocado-Pesto-Pasta", "Pasta", "International", ["Herd","Mixer/Pürierstab"], 10, 10, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Avocado",1,"Stück",G), ("Basilikum",15,"g",GW),
   ("Zitronensaft",1,"EL",SA), ("Olivenöl",2,"EL",FO)],
  "mittel", ["vegan","schnell"])

R("Mac and Cheese glutenfrei", "Pasta", "International", ["Herd","Mixer/Pürierstab"], 15, 15, "mittel", 2,
  [("Maisnudeln",200,"g",ST), ("Cashewkerne",80,"g",NU), ("Karotte",1,"Stück",G),
   ("Kurkuma",0.5,"TL",GW), ("Gemüsebrühe",200,"ml",FL)],
  "mittel", ["vegan"])

R("Blumenkohl-Alfredo-Pasta", "Pasta", "International", ["Herd","Mixer/Pürierstab"], 15, 20, "mittel", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Blumenkohl",300,"g",G), ("Cashewkerne",40,"g",NU),
   ("Knoblauch",2,"Zehen",G), ("Gemüsebrühe",200,"ml",FL)],
  "mittel", ["vegan"])

R("Erbsen-Minze-Pasta mit Ricotta", "Pasta", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Erbsen (TK)",200,"g",G), ("Minze",10,"g",GW),
   ("laktosefreier Ricotta",100,"g",ML), ("Olivenöl",2,"EL",FO)],
  "mittel", [])

R("Rote-Bete-Pasta mit Walnüssen", "Pasta", "International", ["Herd","Mixer/Pürierstab"], 15, 20, "mittel", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Rote Bete gekocht",250,"g",G), ("Walnüsse",30,"g",NU),
   ("laktosefreier Frischkäse",60,"g",ML), ("Olivenöl",2,"EL",FO)],
  "mittel", [])

R("Pasta Arrabbiata", "Pasta", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Tomaten gehackt",400,"g",G), ("Knoblauch",2,"Zehen",G),
   ("Chiliflocken",1,"TL",GW), ("Olivenöl",3,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Kichererbsennudeln mit Spinat & Knoblauch", "Pasta", "Mediterran", ["Herd"], 10, 15, "einfach", 2,
  [("Kichererbsennudeln",200,"g",ST), ("Spinat",150,"g",G), ("Knoblauch",3,"Zehen",G),
   ("Olivenöl",3,"EL",FO), ("Zitronensaft",1,"EL",SA)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Pasta mit Ofentomaten & Oliven", "Pasta", "Mediterran", ["Backofen","Herd"], 10, 25, "einfach", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Kirschtomaten",300,"g",G), ("Oliven",50,"g",G),
   ("Knoblauch",2,"Zehen",G), ("Olivenöl",3,"EL",FO), ("Basilikum",10,"g",GW)],
  "mittel", ["vegan"])

R("Pasta mit Zucchini-Käse-Sauce", "Pasta", "Mediterran", ["Herd"], 15, 15, "einfach", 2,
  [("Maisnudeln",200,"g",ST), ("Zucchini",2,"Stück",G), ("laktosefreier Frischkäse",80,"g",ML),
   ("Knoblauch",1,"Zehe",G), ("Olivenöl",1,"EL",FO)],
  "mittel", [])

R("Pasta mit Radicchio & laktosefreiem Gorgonzola", "Pasta", "Mediterran", ["Herd"], 15, 15, "mittel", 2,
  [("Reisnudeln-Pasta",200,"g",ST), ("Radicchio",150,"g",G), ("laktosefreier Gorgonzola",60,"g",ML),
   ("Walnüsse",20,"g",NU), ("Olivenöl",2,"EL",FO)],
  "hochwertig", [])

R("Reisnudel-Pfanne mit Erdnusssauce Asiatisch", "Pasta", "Asiatisch", ["Herd"], 15, 10, "einfach", 2,
  [("Reisnudeln",200,"g",ST), ("Karotte",1,"Stück",G), ("Erdnussmus",2,"EL",NU),
   ("Kokosaminos",1,"EL",SA), ("Limettensaft",1,"EL",SA), ("Koriander",10,"g",GW)],
  "mittel", ["vegan"])

# ======================= BEILAGEN & SNACKS (15) ============================
R("Ofenkartoffeln mit Kräuterdip", "Snack", "International", ["Backofen"], 10, 35, "einfach", 2,
  [("Kartoffel",500,"g",G), ("Olivenöl",2,"EL",FO), ("laktosefreier Joghurt",100,"g",ML), ("Schnittlauch",1,"EL",GW)],
  "günstig", ["schnell"])

R("Gebackener Blumenkohl mit Sumach", "Snack", "Levantinisch", ["Backofen"], 10, 25, "einfach", 2,
  [("Blumenkohl",400,"g",G), ("Olivenöl",2,"EL",FO), ("Sumach",1,"TL",GW)],
  "günstig", ["vegan"])

R("Rote-Bete-Hummus", "Snack", "Levantinisch", ["Herd","Mixer/Pürierstab"], 10, 0, "einfach", 4,
  [("Rote Bete gekocht",200,"g",G), ("Kichererbsen",250,"g",HP), ("Tahini",2,"EL",NU), ("Zitronensaft",1,"EL",SA)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Klassischer Hummus mit Tahini", "Snack", "Levantinisch", ["Mixer/Pürierstab"], 10, 0, "einfach", 4,
  [("Kichererbsen",400,"g",HP), ("Tahini",2,"EL",NU), ("Zitronensaft",2,"EL",SA), ("Knoblauch",1,"Zehe",G), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan","mealprep-geeignet","schnell"])

R("Süßkartoffel-Pommes aus dem Ofen", "Snack", "International", ["Backofen"], 10, 25, "einfach", 2,
  [("Süßkartoffel",400,"g",G), ("Olivenöl",2,"EL",FO), ("Paprikapulver",1,"TL",GW)],
  "günstig", ["vegan","kinderfreundlich"])

R("Gegrillter Mais mit Limette & Chili", "Snack", "Mexikanisch", ["Herd"], 10, 10, "einfach", 2,
  [("Maiskolben",2,"Stück",G), ("Limettensaft",1,"EL",SA), ("Chilipulver",0.5,"TL",GW), ("Olivenöl",1,"EL",FO)],
  "günstig", ["vegan","schnell"])

R("Gebratener Rosenkohl mit Ahornsirup", "Snack", "International", ["Herd"], 10, 15, "einfach", 2,
  [("Rosenkohl",300,"g",G), ("Ahornsirup",1,"EL",SU), ("Butter laktosefrei",1,"EL",FO)],
  "günstig", ["schnell"])

R("Knusprige geröstete Kichererbsen", "Snack", "International", ["Backofen"], 5, 30, "einfach", 2,
  [("Kichererbsen",400,"g",HP), ("Olivenöl",1,"EL",FO), ("Paprikapulver",1,"TL",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Baba Ganoush (Auberginen-Dip)", "Snack", "Levantinisch", ["Backofen","Mixer/Pürierstab"], 10, 25, "einfach", 4,
  [("Aubergine",2,"Stück",G), ("Tahini",2,"EL",NU), ("Zitronensaft",1,"EL",SA), ("Knoblauch",1,"Zehe",G)],
  "günstig", ["vegan"])

R("Guacamole", "Snack", "Mexikanisch", ["Herd"], 10, 0, "einfach", 2,
  [("Avocado",2,"Stück",G), ("Limettensaft",1,"EL",SA), ("rote Zwiebel",0.25,"Stück",G), ("Koriander",10,"g",GW)],
  "mittel", ["vegan","schnell"])

R("Karotten-Ingwer-Dip", "Snack", "International", ["Herd","Mixer/Pürierstab"], 10, 15, "einfach", 4,
  [("Karotte",300,"g",G), ("Ingwer",1,"Stück",GW), ("Olivenöl",2,"EL",FO)],
  "günstig", ["vegan"])

R("Polenta-Sticks mit laktosefreiem Parmesan", "Snack", "Mediterran", ["Herd","Backofen"], 15, 20, "mittel", 2,
  [("Polenta/Maisgrieß",150,"g",ST), ("laktosefreier Parmesan",40,"g",ML), ("Olivenöl",1,"EL",FO)],
  "mittel", [])

R("Gebackene Zucchini-Sticks mit Mandelpanade", "Snack", "International", ["Backofen"], 15, 20, "mittel", 2,
  [("Zucchini",2,"Stück",G), ("Mandelmehl",60,"g",NU), ("Ei",1,"Stück",HP)],
  "mittel", ["schnell"])

R("Oliven-Tapenade", "Snack", "Mediterran", ["Mixer/Pürierstab"], 10, 0, "einfach", 4,
  [("Oliven",200,"g",G), ("Kapern",1,"EL",SA), ("Knoblauch",1,"Zehe",G), ("Olivenöl",3,"EL",FO)],
  "mittel", ["vegan","schnell"])

R("Rote-Linsen-Cracker glutenfrei", "Snack", "International", ["Backofen"], 15, 20, "mittel", 4,
  [("rote Linsen (gemahlen)",150,"g",HP), ("Olivenöl",2,"EL",FO), ("Sesam",1,"EL",NU), ("Kreuzkümmel",1,"TL",GW)],
  "günstig", ["vegan"])

# ================================ DESSERTS (15) ===============================
R("Schoko-Avocado-Mousse", "Dessert", "International", ["Mixer/Pürierstab"], 10, 60, "einfach", 2,
  [("Avocado",2,"Stück",G), ("Kakaopulver",3,"EL",GW), ("Ahornsirup",3,"EL",SU), ("Hafermilch",50,"ml",FL)],
  "mittel", ["vegan"])

R("Chia-Pudding mit Mango", "Dessert", "International", ["Herd"], 5, 120, "einfach", 2,
  [("Chiasamen",4,"EL",SU), ("Kokosmilch",300,"ml",FL), ("Mango",1,"Stück",G), ("Ahornsirup",1,"EL",SU)],
  "mittel", ["vegan","mealprep-geeignet"])

R("Gebackene Äpfel mit Zimt & Walnüssen", "Dessert", "Deutsch/Alpenländisch", ["Backofen"], 10, 30, "einfach", 2,
  [("Apfel",2,"Stück",G), ("Walnüsse",30,"g",NU), ("Zimt",1,"TL",GW), ("Ahornsirup",2,"EL",SU)],
  "günstig", ["vegan"])

R("Bananen-Nicecream", "Dessert", "International", ["Mixer/Pürierstab"], 5, 0, "einfach", 2,
  [("gefrorene Banane",3,"Stück",G), ("Kakaopulver",1,"EL",GW), ("Hafermilch",50,"ml",FL)],
  "günstig", ["vegan","schnell"])

R("Kokos-Reispudding", "Dessert", "Asiatisch", ["Herd"], 5, 25, "einfach", 2,
  [("Milchreis (glutenfrei)",120,"g",ST), ("Kokosmilch",400,"ml",FL), ("Ahornsirup",2,"EL",SU), ("Zimt",0.5,"TL",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

R("Mandelmehl-Brownies", "Dessert", "International", ["Backofen"], 15, 25, "mittel", 4,
  [("Mandelmehl",150,"g",NU), ("Kakaopulver",50,"g",GW), ("Ei",3,"Stück",HP),
   ("Ahornsirup",100,"g",SU), ("Kokosöl",80,"g",FO)],
  "mittel", [])

R("Beeren-Crumble mit Hafer-Streuseln", "Dessert", "International", ["Backofen"], 15, 30, "einfach", 4,
  [("gemischte Beeren",400,"g",G), ("glutenfreie Haferflocken",100,"g",ST), ("Mandelmehl",50,"g",NU),
   ("Butter laktosefrei",60,"g",FO), ("Ahornsirup",2,"EL",SU)],
  "günstig", ["mealprep-geeignet"])

R("Dattel-Energiebällchen mit Kakao", "Dessert", "International", ["Mixer/Pürierstab"], 15, 0, "einfach", 4,
  [("Datteln",200,"g",SU), ("Mandeln",80,"g",NU), ("Kakaopulver",2,"EL",GW), ("Kokosraspeln",20,"g",SU)],
  "mittel", ["vegan","mealprep-geeignet"])

R("Zitronen-Tarte mit Mandelboden", "Dessert", "Mediterran", ["Backofen"], 25, 30, "schwer", 4,
  [("Mandelmehl",150,"g",NU), ("Ei",3,"Stück",HP), ("Zitronensaft",80,"ml",SA),
   ("Ahornsirup",80,"g",SU), ("Butter laktosefrei",60,"g",FO)],
  "hochwertig", [])

R("Panna Cotta laktosefrei mit Kokosmilch", "Dessert", "Mediterran", ["Herd"], 10, 180, "mittel", 2,
  [("Kokosmilch",300,"ml",FL), ("Vanille",1,"TL",GW), ("Ahornsirup",2,"EL",SU), ("Agar-Agar",1,"TL",SU)],
  "mittel", ["vegan"])

R("Mango-Kokos-Pudding", "Dessert", "Asiatisch", ["Mixer/Pürierstab"], 10, 60, "einfach", 2,
  [("Mango",1,"Stück",G), ("Kokosmilch",200,"ml",FL), ("Chiasamen",2,"EL",SU)],
  "mittel", ["vegan"])

R("Karottenkuchen glutenfrei mit Frischkäse-Frosting", "Dessert", "International", ["Backofen"], 25, 35, "mittel", 6,
  [("Karotte",250,"g",G), ("Mandelmehl",200,"g",NU), ("Ei",3,"Stück",HP),
   ("Ahornsirup",100,"g",SU), ("laktosefreier Frischkäse",150,"g",ML), ("Zimt",1,"TL",GW)],
  "mittel", [])

R("Kürbis-Cheesecake laktosefrei", "Dessert", "International", ["Backofen"], 25, 45, "schwer", 6,
  [("Hokkaido-Kürbis",250,"g",G), ("laktosefreier Frischkäse",300,"g",ML), ("Ei",2,"Stück",HP),
   ("Mandelmehl",100,"g",NU), ("Ahornsirup",80,"g",SU), ("Zimt",1,"TL",GW)],
  "hochwertig", [])

R("Gebackene Birnen mit Honig & Pekannüssen", "Dessert", "International", ["Backofen"], 10, 25, "einfach", 2,
  [("Birne",2,"Stück",G), ("Honig",2,"EL",SU), ("Pekannüsse",30,"g",NU), ("Zimt",0.5,"TL",GW)],
  "günstig", [])

R("Schoko-Kokos-Kugeln", "Dessert", "International", ["Mixer/Pürierstab"], 15, 0, "einfach", 4,
  [("Datteln",150,"g",SU), ("Kokosraspeln",60,"g",SU), ("Kakaopulver",2,"EL",GW)],
  "günstig", ["vegan","mealprep-geeignet"])

# ---------------------------------------------------------------------------
# 4) Export
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Anzahl Rezepte: {len(recipes)}")
    from collections import Counter
    kat_count = Counter(r["kategorie"] for r in recipes)
    print("Pro Kategorie:", dict(kat_count))
    allergen_count = Counter(a for r in recipes for a in r["allergene_enthalten"])
    print("Allergen-Verteilung:", dict(allergen_count))
    vegan_count = sum(1 for r in recipes if r["vegan"])
    print(f"Davon vegan: {vegan_count}")
    ids = [r["id"] for r in recipes]
    assert len(ids) == len(set(ids)), "Doppelte IDs gefunden!"
    names = [r["name"] for r in recipes]
    dupes = [n for n in names if names.count(n) > 1]
    if dupes:
        print("ACHTUNG doppelte Namen:", set(dupes))

    output = {
        "meta": {
            "titel": "Kochplan-App Rezeptdatenbank",
            "stand": "Oktober 2026",
            "anzahl_rezepte": len(recipes),
            "basis_filter_alle_rezepte": {
                "glutenfrei": True, "laktosefrei": True, "fleischfrei": True,
                "fischfrei": True, "sojafrei": True
            }
        },
        "rezepte": recipes
    }
    with open("/home/claude/kochplan/rezepte_200.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("JSON geschrieben: rezepte_200.json")
