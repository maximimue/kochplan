# Kochplan API

Backend einer Essensplaner-App: Wochenplan aus Supermarkt, Küchengeräten, Allergien, Vorlieben und Budget, mit Rezept, Kosten, Dauer und Makros. Aus der gewünschten Essenszeit wird die Startzeit rückwärts berechnet. Clients (später): iOS (SwiftUI/SwiftData, offline-fähig) und Web (React/TS). Solo-Projekt, MVP nur für Eigennutzung.

Sprache: Antworten und Code-Kommentare auf Deutsch, Bezeichner auf Englisch. Antworten knapp und technisch.

Teil des Monorepos `kochplan` (github.com/maximimue/kochplan, public). Dieses Dokument gilt für `server/`; `ios/` und `web/` folgen später als eigene Top-Level-Ordner mit eigenem CLAUDE.md.

## Befehle (alle in `api/`)

```bash
# Lokal: venv mit Python ≥3.12 (das globale Homebrew-pytest hängt an Python 3.9 und scheitert am Import),
# Postgres als Wegwerf-Container:
#   docker run -d --name kochplan-test-pg -e POSTGRES_USER=kochplan -e POSTGRES_PASSWORD=kochplan \
#     -e POSTGRES_DB=kochplan_test -p 5432:5432 postgres:16
pytest -q                                              # braucht Postgres-DB kochplan_test (kochplan/kochplan@localhost)
pytest -q -x tests/test_plans.py::test_name            # einzelner Test
ENV=dev DEV_LOGIN_ENABLED=true uvicorn app.main:app --reload   # Swagger: /docs, POST /v1/auth/dev {email} für Login ohne Apple/Google
alembic revision --autogenerate -m "..."               # danach Migration lesen und prüfen!
alembic upgrade head
python -m app.cli import-ingredients seed/ingredients.json
python -m app.cli import-recipes seed/recipes_batch1.json [--dry-run]   # echter Rezeptbestand
python -m app.cli usage [--month 2026-10]              # KI-Kosten je User
```

Deployment: `docker compose up -d --build`. Der Overlay wird über `COMPOSE_FILE` in `.env` gewählt: `deploy/compose.traefik.yml` (Homelab, DNS-01, nur LAN/NetBird) oder `deploy/compose.caddy.yml` (Oracle, öffentlich).

### Laufende Instanz (Homelab)

- VM `kochplan` auf Proxmox, erreichbar unter `kochplan.lab.syltwerk.de` (Let's-Encrypt via Traefik) bzw. intern `10.10.0.60`, per NetBird-Mesh (Route `10.10.0.0/24` über `lab-core-01`) auch ohne Pi-hole-DNS per `curl --resolve kochplan.lab.syltwerk.de:443:10.10.0.60 ...` erreichbar.
- SSH: `root@10.10.0.60` (Key `s01-infra-admin` ist auf der VM hinterlegt). Deploy-Dir: `~/kochplan` (Git-Checkout von `github.com/maximimue/kochplan`, Repo ist public).
- Update-Zyklus: lokal committen + pushen, dann auf der VM `cd ~/kochplan && git pull --ff-only && cd server && docker compose up -d --build`.

## Struktur

```
api/app/
  config.py      Settings (pydantic-settings, Listen in .env als JSON)
  models.py      alle SQLAlchemy-Modelle
  schemas.py     alle Pydantic-Schemas; RecipeIn = Importformat UND KI-Zielschema
  vocab.py       kontrolliertes Vokabular (Geräte, Allergene, Supermarkt→Preis-Tier, Einheiten)
  errors.py      AppError(code) / Warning_(code) → lokalisiert über i18n
  i18n/de.json   ALLE nutzersichtbaren Texte + Labels
  auth/          Apple/Google-ID-Token-Prüfung (JWKS), eigene JWTs, Refresh-Rotation
  services/      planner, ai, recipes (Import/Kosten), schedule (Startzeit)
  routers/       auth, me, meta, recipes, plans   (Prefix /v1)
api/seed/        ingredients.json (Katalog) + recipes_batch1.json (echter Bestand, 200 Stk.)
                 recipes.json (NUR 4 Test-Fixtures, siehe Regeln unten — nicht erweitern)
api/tests/       pytest, ASGI-Client gegen echtes Postgres
deploy/          Compose-Overlays, Traefik/Caddy, Proxmox-VM- und Bootstrap-Skripte, Backup
tools/recipe_generation/   Generator (generate_recipes.py) + Transform ins RecipeIn-Schema
                 (transform_to_recipein.py) für weitere Rezept-Chargen
```

## Regeln

- Nutzersichtbare Texte nie hart im Code: Code-Key in `i18n/de.json` anlegen, `AppError("code", status, **params)` werfen bzw. `Warning_` zurückgeben.
- Vokabular-Keys sind ASCII/lowercase in `vocab.py`, Labels stehen in `de.json`. Neue Werte immer an beiden Stellen ergänzen.
- Ablauf bei Schema-Änderungen: Model → Schema → `alembic --autogenerate` → Migration prüfen → Test.
- Zeiten sind immer tz-aware und werden in UTC gespeichert. Startzeit nur über `compute_start_at`, das absolut in UTC rechnet (DST-Test existiert).
- Sync-relevante Entities nur soft löschen (`deleted_at`), weil Delta-Sync per `?since=` läuft. Bei Plänen gilt Last-Write-Wins über `client_updated_at`, bei Konflikt kommt 409 mit `server_version`.
- KI läuft nur serverseitig über `AiService`. Jeder Call (auch fehlgeschlagene) wird in `ai_usage` protokolliert, und die Ausgabe wird gegen die User-Constraints geprüft (Allergene, Geräte, Abneigungen). Das Rate-Limit gilt immer, das Monatslimit per `AI_LIMITS_ENABLED`.
- Allergene eines Rezepts = deklarierte ∪ aus dem Zutatenkatalog abgeleitete. Diese Ableitung nie entfernen.
- Neue Endpunkte brauchen Tests. KI-Tests laufen mit `httpx.MockTransport`, ohne echte API-Calls.
- Traefik bekommt keinen Docker-Socket, das Routing kommt aus `deploy/traefik/dynamic.yml`.
- `.env` und `.env.dns` niemals committen.
- `seed/recipes.json` (4 Rezepte) ist fest in `tests/test_plans.py` verdrahtet (exakte Titel-Assertions) — das ist die Test-Fixture, nicht der Rezeptbestand. Der echte Bestand liegt in `seed/recipes_batch1.json` (+ künftige `recipes_batch2.json` usw.) und wird nur in die laufende Instanz importiert, nie in die Tests.

## Getroffene Entscheidungen (nicht neu aufrollen ohne Anlass)

- FastAPI statt NestJS, weil der Cookidoo-Service ohnehin Python ist (`cookidoo-api`). TS-Typen fürs Web werden aus `/openapi.json` generiert.
- Kein Supabase/Firebase: ID-Tokens werden direkt geprüft. Keine automatische Kontoverknüpfung über gleiche E-Mail (Takeover-Risiko).
- Postgres 16 im Container statt Oracle Autonomous DB.
- Kosten sind grob je Preis-Tier (`discount`/`standard`/`bio`), keine Echtzeitpreise.
- `/openapi.json` wird über `app.openapi = _custom_openapi` (in `main.py`) nachbearbeitet: OpenAPI-3.1-Nullable (`anyOf` mit `null`) wird zu 3.0-Stil (`nullable: true`) konvertiert, Dokument als `3.0.3` deklariert — `swift-openapi-generator` 1.14.3 verwirft 3.1-Nullable-Felder sonst komplett. Betrifft nur die ausgelieferte Spezifikation, nicht die Pydantic-Schemas selbst.
- 422-Validierungsfehler laufen über `validation_error_handler` (`errors.py`) und haben dasselbe `{"error": {"code", "message"}}`-Format wie `AppError` — Clients kennen nur ein Fehlerformat.
- Fitness: Tagesbedarf nach Mifflin-St Jeor × PAL-Faktor (`services/fitness.py`), Ziel ±kcal (abnehmen −500, aufbauen +300), Protein je kg (2,0/1,6/2,0), Fett 28 %, Rest Kohlenhydrate. Sicherheitsgrenzen: Mindestalter 18, kein Defizit bei BMI < 18,5, Defizit nie unter 1200/1500/1350 kcal (w/m/d). Zielwerte stehen flach (nullable Skalare) im `ProfileOut`, weil der Swift-Generator nullable `$ref` nicht sauber abbildet. Ziel löschen per `fitness_goal: ""`. Der Planer verteilt das kcal-Ziel nach `MEAL_KCAL_SHARE` auf die Slots eines Tages und wählt zufällig unter den 5 besten Rezepten nach kcal-Nähe + Proteindichte (ohne Ziel unverändert reiner Zufall); verfehlte Ziele werden als Warnung gemeldet statt verschwiegen.
- Ernährungsformen sind hierarchisch (`DIET_ACCEPTS`): vegan erfüllt vegetarisch und pescetarisch, vegetarisch erfüllt pescetarisch.
- Haushalt (`Household`, `services/household.py`, `routers/household.py`): Jeder User gehört genau einem Haushalt (beim ersten Login automatisch angelegt). Gemeinsam: Pläne (`MealPlan.household_id`), Supermarkt, Budget, `household_size` (inkl. Personen ohne App), Geräte. Persönlich: Allergien, Ernährungsform, Abneigungen, Fitness — beim Planen gilt die **Vereinigung** aller Mitglieder (`constraints_for`). `ProfileOut`/`ProfilePatch` lesen/schreiben die gemeinsamen Felder über Properties am `User` durch, die Profil-API blieb dadurch stabil. Beitreten per Einladungscode (8 Zeichen ohne 0/O/1/I/L, 48 h gültig, neuer Code entwertet den alten); ein verlassener Ein-Personen-Haushalt wird samt Plänen gelöscht. KI-Rezepte sind für alle Mitglieder sichtbar (`visible_recipes`).
- Portionen je Person: `PlanEntry.portions = {user_id: Faktor}` (0,5–2,0 in 0,25-Schritten, aus dem Slot-kcal-Ziel des Mitglieds ÷ Rezept-kcal; ohne Ziel 1,0) und `total_portions` = Summe + Personen ohne App. Der Server berechnet sie bei `generate` **und** `PUT` neu, Clients schicken keine Portionen. `PlanEntryOut.my_portion` ist je anfragendem Mitglied. Die Rezeptauswahl orientiert sich am Mittel der Mitglieder-Ziele (`reference_kcal_targets`).
- `current_user` lädt Haushalt und Mitglieder explizit per `joinedload(...).selectinload(...)` — die zyklische Eager-Kette bricht SQLAlchemy sonst ab, und Nachladen scheitert async (`MissingGreenlet`).
- MVP-Hosting: Proxmox-VM im Homelab (Debian 13), nur LAN/NetBird erreichbar, `ENV=dev`. Später Oracle Always Free: dort aktuell 2 OCPU / 12 GB A1, Home-Region Frankfurt, Idle-Reclamation beachten (PAYG-Upgrade).

## Stand

Phase 1 Backend fertig, 46 Tests grün: Auth, Profil, Rezept-Import, Plan-Generierung (DB → KI → Wiederholung), Startzeit, Offline-Sync, KI-Limits/Logging, Konto-Löschung, Fitnessziele (Bedarf, Makros, kcal-bewusste Planung, Warnungen), Haushalt (Einladen/Beitreten/Verlassen, gemeinsame Pläne, vereinigte Allergien, Portionen je Person).

Wichtig für die Fitnessziele: Der aktuelle Rezeptbestand ist komplett vegetarisch/vegan, max. 22 g Protein und ~600 kcal je Portion. Mit Portionen je Person werden kcal-Ziele bis ~3400 auf ±3 % getroffen, Proteinziele aber nur zu ~65 % (Muskelaufbau 160 g → ~105 g) — der Planer meldet das per Warnung. Abhilfe: proteinreiche Charge (Skyr/Quark, Tofu/Tempeh/Seitan, Hülsenfrüchte; optional Fisch/Fleisch mit passenden Diät-Tags) und mehr Frühstücke/Snacks.

Sign in with Apple: `APPLE_AUDIENCES` in der `.env` der VM muss die iOS-Bundle-ID enthalten (steht lokal in `ios/Config/Secrets.xcconfig`, nicht im Repo).

Homelab-Deployment läuft (Traefik + DNS-01, `kochplan.lab.syltwerk.de`, Let's-Encrypt-Zertifikat aktiv, `/healthz` grün).

Rezeptbestand: erste Charge von 200 Rezepten importiert (`seed/recipes_batch1.json`, generiert + ins RecipeIn-Schema übersetzt via `tools/recipe_generation/`), Zutatenkatalog dafür von 24 auf 185 Einträge erweitert. Ziel insgesamt ca. 500 — weitere Chargen über dieselbe Pipeline (`generate_recipes.py` → `transform_to_recipein.py` → `import-recipes --dry-run`).

Als Nächstes:
1. Apple-Token-Revoke bei Kontolöschung (braucht Apple-Client-Secret/p8-Key) — App-Store-Pflicht vor Veröffentlichung.
2. Weitere Rezept-Chargen (ca. 300 fehlen noch bis Ziel 500), Schwerpunkt proteinreich + Frühstück/Snacks (siehe oben).
3. iOS-App (SwiftData-Cache über `/v1/recipes/sync` und `/v1/plans?since=`).

Offen/später: Mitglied aus Haushalt entfernen (bisher kann jedes Mitglied nur selbst gehen), Push-Erinnerungen zur Startzeit, Web-App, Cookidoo-Microservice (inoffiziell, nur Eigennutzung, ToS-Risiko — `cookidoo-api` (miaucl) kann Stand 2026-10 **kein** Rezept anlegen/hochladen, weder im Cookidoo-Konto noch aufs Gerät; nur Login + rein lesendes Cook-Status-Monitoring. Eigene Rezepte ans Thermomix schicken ist damit nicht umsetzbar, bis die Lib das selbst unterstützt — vor erneutem Anlauf dort nachsehen), StoreKit/Stripe-Abo, Portionsfaktor je Person (Bruchteil-Portionen, um hohe kcal-Ziele auch mit vorhandenen Rezepten zu treffen), Gewichtsverlauf.

## Token sparen

- `seed/*.json` und `alembic/versions/*` nicht komplett lesen, sondern gezielt mit `grep` oder `head` arbeiten.
- Tests mit `pytest -q`, bei Fehlern `pytest -q -x tests/<datei>::<test>`.
- Für einen Überblick reichen dieses Dokument und `schemas.py`; nicht jede Datei einzeln öffnen.
