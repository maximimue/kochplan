# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Monorepo `kochplan` (github.com/maximimue/kochplan, **public**). Solo project, MVP for personal use only: a meal-planning app that builds a weekly plan from supermarket, kitchen equipment, allergies, preferences and budget, with recipe cost/duration/macros, and computes a cook's start time backward from the desired eating time.

Sprache: Antworten und Code-Kommentare auf Deutsch, Bezeichner auf Englisch. Antworten knapp und technisch.

## Struktur

- [`server/`](server/CLAUDE.md) — FastAPI-Backend (Postgres, Docker Compose, Homelab/Oracle-Deployment), eigenes ausführliches `CLAUDE.md` mit Stand.
- [`ios/`](ios/CLAUDE.md) — SwiftUI/SwiftData-App „Garnix“, offline-fähig (Wochenplan, Rezepte, Kochmodus, Fitness, Haushalt, HealthKit, Sign in with Apple), eigenes `CLAUDE.md` mit Stand.
- `web/` — React/TS-Web-App. Noch nicht begonnen, kein eigenes Dokument.

Jedes Top-Level-Verzeichnis hat sein eigenes `CLAUDE.md` mit Befehlen, Architektur und Regeln für diesen Teil. **Vor der Arbeit in `server/` oder `ios/` immer zuerst dessen `CLAUDE.md` lesen** — dieses Root-Dokument dupliziert deren Inhalt nicht. Im Server getroffene Design-Entscheidungen (Auth-Modell, kein Supabase/Firebase, Vokabular-Konvention, i18n-Pflicht) gelten sinngemäß auch für `ios/` und später `web/`.

Das Repo ist public: keine Keys, Tokens oder internen Hosts außer bereits dokumentierten committen.
