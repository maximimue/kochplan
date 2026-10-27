# Kochplan API

Backend der Kochplan-App: FastAPI + PostgreSQL in Docker Compose. Läuft im Homelab (Proxmox-VM, amd64) und auf Oracle Cloud Always Free (Ampere A1, arm64).

## Stand (Phase 1 / MVP)

| Bereich | Status |
|---|---|
| Auth: Sign in with Apple / Google (ID-Token-Prüfung gegen JWKS), eigene Access-/Refresh-Tokens mit Rotation + Reuse-Erkennung | ✅ |
| Profil & Onboarding-Daten (Supermarkt, Geräte, Allergene, Ernährungsform, Budget, Haushaltsgröße) | ✅ |
| Feste Rezept-DB mit Import-CLI, Kostenberechnung je Preis-Tier, Allergen-Ableitung aus Zutaten | ✅ |
| Plan-Generierung: DB → KI-Lückenfüller → Wiederholungen, Budget-Steuerung | ✅ |
| Startzeit-Berechnung (UTC, sommerzeitfest) | ✅ |
| Offline-Sync: Rezept-Delta, Plan-Delta, Last-Write-Wins mit 409-Konflikt | ✅ |
| KI: Anthropic serverseitig, Rate-Limit, Nutzungs-/Kosten-Log, Monatslimit (per Flag) | ✅ |
| Konto-Löschung (App-Store-Pflicht) | ✅ |
| i18n: stabile Fehler-/Warnungs-Codes + lokalisierte Texte, Labels über `/v1/meta/vocab` | ✅ (nur `de`) |
| StoreKit/Stripe, Cookidoo-Service, Push-Erinnerungen | später (Phase 3/4) |

## Lokal entwickeln

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
createdb kochplan && createdb kochplan_test          # lokales Postgres 16
alembic upgrade head
python -m app.cli import-ingredients seed/ingredients.json
python -m app.cli import-recipes seed/recipes.json
ENV=dev DEV_LOGIN_ENABLED=true uvicorn app.main:app --reload
# Swagger: http://localhost:8000/docs   ·   Tests: pytest
```

## Deployment im Homelab (Proxmox, MVP)

Server ist nur im LAN bzw. per NetBird erreichbar — keine Portfreigabe. Trotzdem gültiges HTTPS (Pflicht für iOS/ATS) über Let's Encrypt **DNS-01** via Traefik.

1. **VM anlegen** (auf dem Proxmox-Host):
   ```bash
   VMID=210 STORAGE=local-lvm BRIDGE=vmbr0 IP=192.168.178.60/24 GW=192.168.178.1 \
   SSH_KEY=/root/max.pub bash deploy/homelab/create-vm.sh
   ```
   Debian 13 Cloud-Image (SHA512-geprüft), 2 vCPU, 4 GB RAM, 32 GB, Autostart, Guest-Agent.
2. **In der VM**:
   ```bash
   git clone <repo> kochplan-server && sudo bash kochplan-server/deploy/homelab/bootstrap-debian.sh
   # neu einloggen
   cd kochplan-server
   cp .env.example .env && cp .env.dns.example .env.dns && nano .env .env.dns
   docker compose up -d --build
   docker compose exec api python -m app.cli import-ingredients seed/ingredients.json
   docker compose exec api python -m app.cli import-recipes seed/recipes.json
   ```
3. **DNS intern**: `kochplan.lab.syltwerk.de` → VM-IP als lokaler Eintrag im Pi-hole. Unterwegs per NetBird: Nameserver-Gruppe für `lab.syltwerk.de` auf den Pi-hole zeigen lassen.
   Alternativ öffentlicher A-Record auf die private IP — dann aber den FritzBox-DNS-Rebind-Schutz für die Domain freischalten.
4. **Backup**: Proxmox-Backupjob für die VM + täglicher `pg_dump` (Cron). `BACKUP_DIR` in `/etc/cron.d/kochplan-backup` auf einen NFS-Mount vom TrueNAS legen.
5. **Test**: `curl https://kochplan.lab.syltwerk.de/healthz`, Swagger unter `/docs` (nur `ENV=dev`).

Später nach Oracle umziehen: `COMPOSE_FILE` auf `compose.caddy.yml` umstellen, `pg_dump`/`pg_restore`, DNS umbiegen.

## Deployment auf Oracle Cloud (Always Free)

1. **Account anlegen, Home-Region `Germany Central (Frankfurt)` wählen** — lässt sich später nicht ändern, Always-Free-Ressourcen gibt es nur dort.
2. **Instanz**: Ubuntu 24.04 (aarch64), Shape `VM.Standard.A1.Flex`, **2 OCPU / 12 GB** (aktuelles Free-Limit), Boot-Volume 100 GB, Public IPv4, eigenen SSH-Key hinterlegen.
   Bei „Out of host capacity“: andere Availability Domain oder später erneut versuchen.
3. **Security List** des Subnetzes: Ingress TCP 80, 443 und UDP 443 von `0.0.0.0/0`.
4. Auf der Instanz:
   ```bash
   git clone <repo> kochplan-server && cd kochplan-server
   sudo bash deploy/bootstrap-oci.sh       # Docker, iptables, Swap, Auto-Updates, Backup-Cron
   # neu einloggen
   cp .env.example .env && nano .env       # COMPOSE_FILE=…compose.caddy.yml, ENV=prod, DEV_LOGIN_ENABLED=false
   docker compose up -d --build
   docker compose exec api python -m app.cli import-ingredients seed/ingredients.json
   docker compose exec api python -m app.cli import-recipes seed/recipes.json
   ```
5. DNS: A-Record `API_DOMAIN` → Public IP. Caddy holt das Zertifikat automatisch.

## API-Überblick (`/v1`)

| Methode | Pfad | Zweck |
|---|---|---|
| POST | `/auth/apple`, `/auth/google` | ID-Token gegen eigene Tokens tauschen |
| POST | `/auth/refresh`, `/auth/logout`, `/auth/logout-all` | Session-Verwaltung |
| GET/PATCH/DELETE | `/me` | Profil lesen, ändern, Konto löschen |
| GET | `/meta/vocab` | Auswahllisten + Labels fürs Onboarding |
| GET | `/recipes/sync?since=` | Delta-Sync für den Offline-Cache |
| GET | `/recipes`, `/recipes/{id}` | Suche/Detail (standardmäßig nur passende Rezepte) |
| POST | `/recipes/generate` | KI-Rezept auf Wunsch |
| POST | `/plans/generate` | Wochenplan aus Slots (Tag, Mahlzeit, Essenszeit) |
| GET | `/plans?since=`, `/plans/{week_start}` | Pläne bzw. Delta inkl. gelöschter |
| PUT/DELETE | `/plans/{week_start}` | Offline-Änderung hochladen (LWW) / Soft-Delete |

## Rezept-Format (für die festen Rezepte)

Siehe `api/seed/recipes.json` und `api/seed/ingredients.json` — identisch mit dem Zielschema der KI (`RecipeIn` in `app/schemas.py`).

- Mengen in `g | kg | ml | l | el | tl | stk | bund | prise`; Zutatenpreise in Cent je `kg | l | stk` und Tier (`discount`, `standard`, `bio`)
- Allergene: 14 EU-Hauptallergene + `laktose`; zusätzlich automatisch aus dem Zutatenkatalog ergänzt
- Dauer getrennt nach `prep` (aktiv), `cook` (aktiv am Gerät), `passive` (Backen/Ruhen) — Startzeit nutzt die Summe
- Thermomix-Schritte optional mit `time_s`, `temp_c`, `speed`
- `import-recipes --dry-run` prüft eine Datei, ohne zu speichern, und meldet fehlende Zutaten/Einheitenkonflikte

## Designentscheidungen

- **Python/FastAPI** statt NestJS: Cookidoo-Anbindung ist ohnehin Python (`cookidoo-api`), KI-Ökosystem, ein Laufzeit-Stack auf der kleinen VM. TS-Typen für Web lassen sich aus `/openapi.json` generieren.
- **Kein Supabase/Firebase**: Apple/Google-Tokens werden direkt geprüft. Keine Drittanbieter-Abhängigkeit, keine zusätzliche Auftragsverarbeitung, Daten bleiben in Frankfurt.
- **Keine automatische Konto-Verknüpfung per E-Mail** (Takeover-Risiko, Apple liefert oft Relay-Adressen).
- **KI-Ausgaben werden serverseitig gegengeprüft** (Allergene, Geräte, Abneigungen) und bei Verstoß verworfen.
- **Postgres im Container** statt Oracle Autonomous DB: portabel, kein Vendor-Lock-in, Free-ADB ist auf 20 Sessions begrenzt.
