# Garnix (iOS)

Native iOS-Client der Kochplan-App, Produktname **Garnix** (Essensplaner: Wochenplan aus Supermarkt, Küchengeräten, Allergien, Vorlieben, Budget; Rezept mit Kosten, Dauer, Makros; Startzeit = Essenszeit − Dauer). Spricht ausschließlich mit dem eigenen Backend (`server/`, FastAPI). Offline-first: Die App muss ohne dauerhafte Internetverbindung voll nutzbar sein. Solo-Projekt, MVP nur für Eigennutzung.

Sprache: Antworten und Code-Kommentare auf Deutsch, Bezeichner auf Englisch. Antworten knapp und technisch.

Teil des Monorepos `kochplan` (github.com/maximimue/kochplan, public). Dieses Dokument gilt für `ios/`. Backend-Details stehen in `server/CLAUDE.md`, und dort getroffene Entscheidungen gelten auch hier.

## Entwicklungsumgebung

- Entwicklung lokal auf dem Mac in **Xcode** (aktuelle Version). Xcode ist die primäre Umgebung: Bauen, Debuggen, Previews, Signing, Capabilities, Deployment aufs eigene iPhone.
- Claude Code arbeitet parallel im selben Checkout und ändert Dateien auf der Platte, die Xcode automatisch nachlädt. Claude Code nutzt `xcodebuild` nur zur Verifikation (Build/Test) und ersetzt Xcode nicht.
- Das `.xcodeproj` wird in Xcode gepflegt und committet. Es nutzt synchronisierte Ordner (Buildable Folders), daher landen neue Swift-Dateien in den Feature-Ordnern automatisch im Target.
- `project.pbxproj` nie von Hand bearbeiten. Wenn eine Änderung am Projekt nötig ist (neues Target, SPM-Paket, Capability, Build-Phase), beschreibt Claude Code den Schritt und der Nutzer erledigt ihn in Xcode. Build-Settings kommen bevorzugt aus `Config/*.xcconfig`.
- Signing (Team, Provisioning) erfolgt ausschließlich lokal in Xcode bzw. über die gitignorte `Config/Secrets.xcconfig`.

## Zielplattform & Stack

- iOS 18+ (Deployment Target), iPhone zuerst; iPad soll nur sauber skalieren, ohne eigenes Layout.
- Gebaut mit aktuellem Xcode-SDK, damit iOS-26-Geräte automatisch das neue Systemdesign (Liquid Glass) bekommen.
- Swift 6, Strict Concurrency (`complete`), SwiftUI-only (UIKit nur, wo kein SwiftUI-Pendant existiert).
- Persistenz: SwiftData. State: `@Observable` (kein `ObservableObject`/Combine, kein TCA).
- Netzwerk: `swift-openapi-generator` (Build-Plugin) + `swift-openapi-urlsession`, generiert aus `/openapi.json` des Servers.
- Auth: `AuthenticationServices` (Sign in with Apple) und `GoogleSignIn` (SPM).
- Charts: Swift Charts (Makros). Tests: Swift Testing (`@Test`), UI-Tests mit XCTest.
- Keine weiteren Third-Party-Abhängigkeiten ohne Rückfrage.

## Befehle (alle in `ios/`)

In Xcode: `⌘R` (Run), `⌘U` (Tests), Previews im Canvas.

Für Claude Code zur Verifikation:

```bash
./scripts/fetch-openapi.sh                                # holt openapi.json vom Server → Garnix/Core/API/openapi.json
xcodebuild -project Garnix.xcodeproj -scheme Garnix -destination 'platform=iOS Simulator,name=iPhone 16' build
xcodebuild -project Garnix.xcodeproj -scheme Garnix -destination 'platform=iOS Simulator,name=iPhone 16' test
xcodebuild ... test -only-testing:GarnixTests/SyncEngineTests   # einzelne Suite
```

Wenn der Simulator-Name nicht existiert: `xcrun simctl list devices available` prüfen, nicht raten. Zusätzlich gelegentlich auf einem iOS-18-Simulator testen, damit die Fallbacks greifen.

### Backend für die Entwicklung

- Lokal: `server/api` mit `ENV=dev DEV_LOGIN_ENABLED=true uvicorn app.main:app --reload` (Swagger unter `/docs`). Der Simulator erreicht den Mac über `localhost`.
- Homelab: `https://kochplan.lab.syltwerk.de`, erreichbar nur über LAN/NetBird. Auf dem echten iPhone muss NetBird laufen.
- Base-URL kommt aus `Config/*.xcconfig` (`API_BASE_URL`) über `Info.plist` und wird nie im Code hart verdrahtet. `Debug` → localhost/Homelab, `Release` → später Oracle.
- Dev-Login (`POST /v1/auth/dev {email}`) nur in `#if DEBUG` anbieten.

## Struktur

```
ios/
  Garnix.xcodeproj
  Config/            Debug.xcconfig, Release.xcconfig, Secrets.xcconfig (gitignored)
  scripts/           fetch-openapi.sh
  Garnix/
    App/             GarnixApp, RootView, AppEnvironment (DI über SwiftUI-Environment)
    Core/
      API/           openapi.json, openapi-generator-config.yaml, APIClient (Wrapper: Auth-Header, Refresh, Fehler-Mapping)
      Auth/          AuthService, AppleSignIn, GoogleSignIn, KeychainStore
      Persistence/   SwiftData-Models, ModelContainer-Setup, Mapper DTO ↔ Entity
      Sync/          SyncEngine (@ModelActor), SyncState, ConflictResolver
      Schedule/      StartTimeCalculator, NotificationScheduler (lokale Notifications)
      Meta/          Vokabular + Labels aus /v1/meta (gecacht)
    Features/
      Onboarding/    Login → Supermarkt → Geräte → Allergien/Vorlieben → Budget
      WeekPlan/      Wochenübersicht, Plan generieren, Tag-Detail, Kochtermine
      Recipes/       Liste/Suche/Filter, Detail
      Cooking/       Kochmodus (Schritt für Schritt)
      Profile/       Profil, Einstellungen, Sync-Status, Konto löschen
    DesignSystem/    Tokens (Farben, Spacing, Radius, Typo), Komponenten, Availability-Modifier
    Resources/       Localizable.xcstrings, Assets.xcassets
  GarnixTests/
  GarnixUITests/
```

Jedes Feature ist ein eigener Ordner mit `*View`, optional `*Model` (`@Observable`) und eigenen Subviews. Views bleiben klein (eine View ≈ ein Screen-Abschnitt) und haben `#Preview` mit In-Memory-ModelContainer und Fixture-Daten, damit sie im Xcode-Canvas ohne Backend laufen.

## Design (modernes Layout)

Ziel ist eine native, ruhige Ästhetik, die den System-Komponenten folgt, statt eigene Chrome nachzubauen. Basis ist iOS 18. Auf iOS 26 übernehmen Systemkomponenten Liquid Glass automatisch.

- **Materialien**: Auf iOS 18 kommen Materialien zum Einsatz (`.regularMaterial`, `.ultraThinMaterial`). Eigene Glas-Effekte für schwebende Elemente (z. B. Kochmodus-Steuerung) nur über einen zentralen Modifier in `DesignSystem` (z. B. `.floatingSurface()`), der intern per `if #available(iOS 26, *)` Liquid Glass nutzt und sonst auf Material zurückfällt. Keine `#available`-Weichen verstreut in Feature-Views.
- **Navigation**: `TabView` mit `Tab`-API: *Woche*, *Rezepte* (mit Suche), *Profil*. Pro Tab ein `NavigationStack` mit typisierten Routen (`navigationDestination(for:)`). iOS-26-only-Verhalten (z. B. Tab-Bar minimieren beim Scrollen) nur über `DesignSystem`-Modifier mit Fallback.
- **Woche**: horizontal scrollbare Tageskarten oben, darunter die Gerichte des gewählten Tages als große Karten (Bild bzw. Platzhalter-Gradient, Titel, Dauer, Kosten, kcal) plus prominenter Hinweis „Starten um 17:40“. Leerer Zustand mit CTA „Plan erstellen“.
- **Rezept-Detail**: Hero-Bereich, Kennzahlen-Chips (Dauer, Kosten, kcal, Geräte), Makros als kleines Swift-Charts-Diagramm (Protein/Fett/KH), Zutaten mit Portionen-Stepper, Schritte nummeriert. Badge „Offline verfügbar“ bzw. „Braucht Internet“ (KI-Rezepte vor dem Caching). Allergene deutlich, aber neutral markieren.
- **Kochmodus**: Vollbild, ein Schritt pro Seite, große Schrift, Swipe/Buttons, integrierte Timer, Bildschirm bleibt an (`isIdleTimerDisabled`).
- **Onboarding**: mehrstufig mit Fortschrittsanzeige, Auswahl über große, antippbare Kacheln (Geräte/Supermärkte mit SF Symbols), jederzeit im Profil änderbar.
- **Grundregeln**: Dark Mode, Dynamic Type bis AX-Größen (keine fixen Höhen bei Text), VoiceOver-Labels, SF Symbols, `ContentUnavailableView` für Leer- und Fehlerzustände, Haptik sparsam (`sensoryFeedback`). Farben/Abstände nur über `DesignSystem`-Tokens, keine Magic Numbers in Views. Akzentfarbe über `AccentColor` im Asset-Katalog.
- Animationen dezent (`.smooth`, `matchedTransitionSource` + `.navigationTransition(.zoom)` von Karte zu Detail).

## Regeln

- **Verfügbarkeit**: Jede API über iOS 18 hinaus nur mit `#available` und Fallback, gekapselt in `DesignSystem` oder `Core`. Der Build muss gegen iOS 18 ohne Warnungen durchlaufen.
- **Texte**: Nutzersichtbare Texte nie hart im Code, sondern nur über `Localizable.xcstrings` mit semantischen Keys (`weekplan.empty.title`). UI vorerst nur Deutsch, Struktur aber mehrsprachig.
- **Vokabular** (Geräte, Allergene, Supermärkte, Einheiten): Keys sind ASCII/lowercase wie in `server/api/app/vocab.py`. Labels kommen aus `/v1/meta` und werden lokal gecacht, nie in der App dupliziert. Unbekannte Keys tolerant darstellen (Fallback = Key), nicht crashen.
- **Fehler**: Der Server liefert lokalisierte `AppError`-Meldungen und Warnungen. Die App zeigt die Server-Meldung an und mappt nur Transportfehler (offline, Timeout) auf eigene Texte.
- **API**: Nur über den generierten Client und den `APIClient`-Wrapper. Keine manuellen `URLSession`-Calls und keine handgeschriebenen DTOs, die das OpenAPI-Schema duplizieren. Bei Server-Schemaänderungen erst `fetch-openapi.sh` ausführen, dann bauen.
- **KI**: Die App ruft nie direkt eine KI-API auf, nur Backend-Endpunkte. KI-Rezepte werden nach Erhalt sofort in SwiftData gecacht.
- **Auth**: Access- und Refresh-Token ausschließlich in der Keychain (`kSecAttrAccessibleAfterFirstUnlock`), nie in UserDefaults oder SwiftData. Refresh-Rotation wie vom Server vorgegeben: Bei 401 genau ein Refresh-Versuch (serialisiert, kein paralleles Refreshen), danach Logout. Keine Kontoverknüpfung über E-Mail.
- **Zeiten**: Intern immer `Date` (absolut, entspricht UTC auf dem Server), Anzeige in `TimeZone.current`. Die Startzeit liefert der Server (`compute_start_at`). Offline berechnet `StartTimeCalculator` sie vorläufig als `eatAt − duration` absolut, ohne Kalenderarithmetik über DST. Nach dem Sync gilt der Serverwert. Für den DST-Fall gibt es einen Test.
- **Erinnerungen**: Lokale Notifications zur Startzeit über `NotificationScheduler`, bei jeder Plan- oder Terminänderung neu planen (idempotent über stabile Identifier). Server-Push kommt später.
- **Concurrency**: UI-Code `@MainActor`. Sync und Import laufen im `@ModelActor`. `ModelContext` und Models nie über Actor-Grenzen reichen, nur `PersistentIdentifier` oder DTOs. Keine `@unchecked Sendable`-Workarounds ohne Begründung im Kommentar.
- **Logging**: Kein `print`, sondern `Logger` (os) mit Subsystem `Bundle.main.bundleIdentifier` und Kategorien je Modul.

## Offline-Sync

- Rezepte: `GET /v1/recipes/sync` (Delta). Beim ersten Start komplett, danach inkrementell.
- Pläne: `GET /v1/plans?since=<lastSync>`. Lokale Änderungen werden mit `client_updated_at` hochgeschickt. Bei **409** liefert der Server `server_version`, dann gilt Last-Write-Wins wie serverseitig, die Serverversion übernehmen und den Nutzer dezent informieren.
- Jede sync-relevante Entity hat `serverID`, `updatedAt`, `deletedAt` (Soft-Delete, Tombstones lokal behalten bis bestätigt) und `isDirty`.
- Sync-Trigger: App-Start, Rückkehr in den Vordergrund, Netzwechsel (`NWPathMonitor`), Pull-to-Refresh. Kein Dauer-Polling.
- Die UI liest ausschließlich aus SwiftData (`@Query`), nie direkt aus API-Antworten. Netzwerk füllt nur den Store.
- Sync-Status (zuletzt synchronisiert, ausstehende Änderungen, Offline) ist im Profil sichtbar.

## Tests

- Neue Logik braucht Tests. Pflicht sind: `StartTimeCalculator` (inkl. DST), `SyncEngine` (Delta, Soft-Delete, 409), Token-Refresh, DTO↔Entity-Mapper.
- Netzwerk in Tests über einen Mock-`ClientTransport` des OpenAPI-Runtimes, ohne echte Calls und ohne Abhängigkeit vom Homelab.
- SwiftData in Tests nur mit `ModelConfiguration(isStoredInMemoryOnly: true)`.
- UI-Tests nur für Kernflows (Onboarding per Dev-Login, Plan erstellen, Rezept öffnen, Kochmodus).

## Getroffene Entscheidungen (nicht neu aufrollen ohne Anlass)

- iOS 18 als Minimum, Liquid Glass auf iOS 26 nur über gekapselte `#available`-Weichen.
- Lokale Entwicklung in Xcode. Das `.xcodeproj` mit synchronisierten Ordnern ist die Wahrheit, Claude Code ändert es nicht direkt.
- API-Client generiert aus OpenAPI, analog zu den TS-Typen im Web.
- Kein Firebase/Supabase-SDK, weil der Server ID-Tokens direkt prüft.
- Thermomix/Cookidoo ist nicht Teil des iOS-MVP und läuft später ausschließlich über den Server-Microservice.
- `swift-openapi-generator` 1.14.3 verwirft OpenAPI-3.1-Nullable-Felder (`anyOf: [Typ, null]`) komplett statt sie als optional zu erzeugen — betrifft u. a. `kcal`, `protein_g`, Zutatenmengen. Server liefert `/openapi.json` deshalb direkt im 3.0-Stil (`nullable: true`, siehe `app/main.py::_custom_openapi` im Server), kein Nachbearbeiten im Client nötig.

## Konfiguration

- Bundle-ID, Team-ID und Google-Client-IDs stehen nur in `Config/Secrets.xcconfig` (gitignored) und werden über `PRODUCT_BUNDLE_IDENTIFIER` bzw. `Info.plist`-Variablen eingebunden. Die Bundle-ID muss identisch in `APPLE_AUDIENCES` des Servers stehen.
- Im Code und in Dokumenten nie eine konkrete Bundle-ID hart verdrahten.
- Capability „Sign in with Apple“ wird in Xcode aktiviert.
- Das Repo ist public, also keine Keys, IDs oder internen Hosts außer der dokumentierten Homelab-Domain committen.

## Stand

Noch kein Code. Reihenfolge:
1. Xcode-Projekt (vom Nutzer in Xcode angelegt, synchronisierte Ordner, xcconfigs eingebunden), Ordnerstruktur, DesignSystem-Tokens inkl. Availability-Modifier, TabView-Skelett mit Previews.
2. OpenAPI-Client + `APIClient` + Dev-Login + Keychain.
3. SwiftData-Models + `SyncEngine` (Rezepte, dann Pläne) + Tests.
4. Rezepte-Tab (Liste, Suche, Filter, Detail).
5. Onboarding/Profil gegen `/v1/me` und `/v1/meta`.
6. Woche: Plan generieren, Kochtermine, Startzeit, lokale Notifications.
7. Kochmodus.
8. Sign in with Apple + Google (sobald serverseitig konfiguriert).

Offen/später: Einkaufsliste, Server-Push, StoreKit-Abo, Widgets/Live Activity für „Jetzt starten“, Fitness-Modul (Makros sind bereits vorhanden), Thermomix-Sync-Anzeige.

## Token sparen

- Generierten OpenAPI-Code, `openapi.json` und `project.pbxproj` nicht komplett lesen. Gezielt mit `grep` arbeiten.
- Für Server-Verhalten erst `server/CLAUDE.md` und `server/api/app/schemas.py` lesen, nicht den ganzen Server.
- Builds und Tests mit `-quiet` bzw. gefilterter Ausgabe (`| xcbeautify`, falls installiert) laufen lassen. Bei Fehlern nur die betroffene Suite erneut ausführen.
