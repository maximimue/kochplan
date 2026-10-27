# Kochplan API

Backend einer Essensplaner-App: Wochenplan aus Supermarkt, Küchengeräten, Allergien, Vorlieben und Budget, mit Rezept, Kosten, Dauer und Makros. Aus der gewünschten Essenszeit wird die Startzeit rückwärts berechnet. Clients (später): iOS (SwiftUI/SwiftData, offline-fähig) und Web (React/TS). Solo-Projekt, MVP nur für Eigennutzung.

Sprache: Antworten und Code-Kommentare auf Deutsch, Bezeichner auf Englisch. Antworten knapp und technisch.

Teil des Monorepos `kochplan` (github.com/maximimue/kochplan, public). Dieses Dokument gilt für `server/`; `ios/` und `web/` folgen später als eigene Top-Level-Ordner mit eigenem CLAUDE.md.

## Befehle (alle in `api/`)

```bash
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
- MVP-Hosting: Proxmox-VM im Homelab (Debian 13), nur LAN/NetBird erreichbar, `ENV=dev`. Später Oracle Always Free: dort aktuell 2 OCPU / 12 GB A1, Home-Region Frankfurt, Idle-Reclamation beachten (PAYG-Upgrade).

## Stand

Phase 1 Backend fertig, 26 Tests grün: Auth, Profil, Rezept-Import, Plan-Generierung (DB → KI → Wiederholung), Startzeit, Offline-Sync, KI-Limits/Logging, Konto-Löschung.

Homelab-Deployment läuft (Traefik + DNS-01, `kochplan.lab.syltwerk.de`, Let's-Encrypt-Zertifikat aktiv, `/healthz` grün).

Rezeptbestand: erste Charge von 200 Rezepten importiert (`seed/recipes_batch1.json`, generiert + ins RecipeIn-Schema übersetzt via `tools/recipe_generation/`), Zutatenkatalog dafür von 24 auf 185 Einträge erweitert. Ziel insgesamt ca. 500 — weitere Chargen über dieselbe Pipeline (`generate_recipes.py` → `transform_to_recipein.py` → `import-recipes --dry-run`).

Als Nächstes:
1. Sign in with Apple konfigurieren (Bundle-ID in `APPLE_AUDIENCES`).
2. Weitere Rezept-Chargen (ca. 300 fehlen noch bis Ziel 500).
3. iOS-App (SwiftData-Cache über `/v1/recipes/sync` und `/v1/plans?since=`).

Offen/später: Apple-Token-Revoke bei Kontolöschung, Push-Erinnerungen zur Startzeit, Web-App, Cookidoo-Microservice (inoffiziell, nur Eigennutzung, ToS-Risiko), StoreKit/Stripe-Abo, Fitness-Modul (Makros sind bereits je Rezept vorhanden).

## Token sparen

- `seed/*.json` und `alembic/versions/*` nicht komplett lesen, sondern gezielt mit `grep` oder `head` arbeiten.
- Tests mit `pytest -q`, bei Fehlern `pytest -q -x tests/<datei>::<test>`.
- Für einen Überblick reichen dieses Dokument und `schemas.py`; nicht jede Datei einzeln öffnen.
