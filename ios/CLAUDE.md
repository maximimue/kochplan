# Garnix (iOS)

Native iOS-Client der Kochplan-App, Produktname **Garnix** (Essensplaner: Wochenplan aus Supermarkt, Küchengeräten, Allergien, Vorlieben, Budget; Rezept mit Kosten, Dauer, Makros; Startzeit = Essenszeit − Dauer). Spricht ausschließlich mit dem eigenen Backend (`server/`, FastAPI). Offline-first: Die App muss ohne dauerhafte Internetverbindung voll nutzbar sein. Solo-Projekt, MVP nur für Eigennutzung.

Sprache: Antworten und Code-Kommentare auf Deutsch, Bezeichner auf Englisch. Antworten knapp und technisch.

Teil des Monorepos `kochplan` (github.com/maximimue/kochplan, public). Dieses Dokument gilt für `ios/`. Backend-Details stehen in `server/CLAUDE.md`, und dort getroffene Entscheidungen gelten auch hier.

## Entwicklungsumgebung

- Entwicklung lokal auf dem Mac in **Xcode** (aktuelle Version). Xcode ist die primäre Umgebung: Bauen, Debuggen, Previews, Signing, Capabilities, Deployment aufs eigene iPhone.
- Claude Code arbeitet parallel im selben Checkout und ändert Dateien auf der Platte, die Xcode automatisch nachlädt. Claude Code nutzt `xcodebuild` nur zur Verifikation (Build/Test) und ersetzt Xcode nicht.
- Das `.xcodeproj` wird in Xcode gepflegt und committet. Es nutzt synchronisierte Ordner (Buildable Folders), daher landen neue Swift-Dateien in den Feature-Ordnern automatisch im Target.
- `project.pbxproj` nie von Hand bearbeiten. Wenn eine Änderung am Projekt nötig ist (neues Target, SPM-Paket, Capability, Build-Phase), beschreibt Claude Code den Schritt und der Nutzer erledigt ihn in Xcode. Build-Settings kommen bevorzugt aus `Config/*.xcconfig`.
- Signing (Team, Provisioning) erfolgt in Xcode; die resultierenden Werte in `project.pbxproj` werden mit committet.

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
- **Texte**: Nutzersichtbare Texte nie hart im Code, sondern nur über `Localizable.xcstrings` mit semantischen Keys (`weekplan.empty.title`). UI vorerst nur Deutsch, Struktur aber mehrsprachig. Interpolation in einem Key-Literal (`Text("key \(n)")`) erzeugt den Format-Key `key %lld` — der muss genau so im Katalog stehen. Dynamisch zusammengesetzte Keys erst als `String` bauen und dann `LocalizedStringKey(string)` übergeben, im Katalog mit `extractionState: manual`.
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

- Team-ID und Bundle-ID setzt Xcode beim Signing in `project.pbxproj` — bewusst akzeptiert und committet, beide sind nicht geheim (Team-ID steht in jeder signierten App, Bundle-ID ist öffentlich). Die Bundle-ID muss identisch in `APPLE_AUDIENCES` des Servers stehen.
- Echte Geheimnisse (Google-Client-IDs, API-Keys) nur in `Config/Secrets.xcconfig` (gitignored), eingebunden über `Info.plist`-Variablen. Im Swift-Code keine Bundle-ID hart verdrahten.
- Capability „Sign in with Apple“ wird in Xcode aktiviert.
- Das Repo ist public, also keine Keys, IDs oder internen Hosts außer der dokumentierten Homelab-Domain committen.

## Stand

Erledigt:
1. Xcode-Projekt, Ordnerstruktur, DesignSystem-Tokens inkl. `.floatingSurface()`, TabView-Skelett mit Previews.
2. OpenAPI-Client + `APIClient` (Auth-Middleware, Refresh-Retry, Fehler-Mapping) + Dev-Login + Keychain.
3. SwiftData-Model `Recipe` + `RecipeMapper` + `SyncEngine` (Delta-Sync, Soft-Delete) für Rezepte, Tests grün.
4. Rezepte-Tab (Liste, Suche nach Titel, Filter nach Mahlzeit-Typ, Detail mit Makro-Chart/Zutaten-Stepper/Schritten).
5. `VocabCache` (`/v1/meta/vocab`, gecacht, tolerante Fallbacks) + `ProfileStore` (`/v1/me`) + Onboarding-Flow (Supermarkt/Geräte/Allergien+Vorlieben/Budget) + Profil-Ansicht mit Bearbeiten/Konto-löschen/Sync-Status.
6. `StartTimeCalculator` (inkl. DST-Test) + SwiftData-Model `MealPlan`/`PlanEntry` + `PlanMapper` + Pläne-Sync (Delta, Soft-Delete, pull-only) + `NotificationScheduler` (lokale Erinnerungen, idempotent) + Woche-Tab (Tageskarten, Plan generieren, „Starten um“-Hinweis).
7. `CookingModeView` (Vollbild, ein Schritt pro Seite, Swipe + Buttons, Pro-Schritt-Timer, Bildschirm bleibt an). Einstieg aus Rezept-Detail und aus der Woche-Ansicht (Plan-Karte antippen).
8. Favoriten (`Recipe.isFavorite`, rein lokal, vom Sync nicht angefasst) + Einkaufsliste (`ShoppingListBuilder`, aus bereits synchronisierten Plan-/Rezeptdaten berechnet, kein eigener Server-Endpunkt) + Gericht tauschen (Swipe-Action auf der Plan-Karte → Katalog-Auswahl → `SyncEngine.putPlan`, reaktiviert den PUT-Pfad inkl. 409/Last-Write-Wins).
9. Mehrere Mahlzeiten pro Tag (1–5 je Wochentag, Stepper beim Erstellen/Neu-Erstellen über Toolbar-Kreispfeil) + Tagesübersicht (Makros **je Person** über `DayNutrition`, Kosten je Haushalt) + Server-Hinweise der Generierung als Banner.
10. Fitness: `FitnessSurveyView` (Ziel → Körperdaten → Aktivität → Ergebnis), erscheint einmalig nach dem Onboarding bzw. für Bestandsnutzer ohne Ziel (`@AppStorage("fitness.surveyHandled")`), danach über Profil → „Fitnessziel bearbeiten“. Zielwerte (`target_kcal`, `target_protein_g`, …, `recommended_meals_per_day`) berechnet ausschließlich der Server; die App spiegelt nur die Eingabegrenzen. Wochenplan-Stepper starten mit `recommended_meals_per_day`, die Tagesübersicht zeigt Fortschritt gegen kcal-/Proteinziel. Ziel löschen = `fitness_goal: ""` (der generierte Client kann kein explizites null senden).

`PUT /v1/plans/{week_start}` wird jetzt genutzt (nur für den Tausch-Fall: komplette Eintragsliste neu geschickt, bei 409 übernimmt der Client automatisch `server_version`). Allgemeines freies Bearbeiten einzelner Felder (Uhrzeit, Portionen etc.) bzw. ein echtes `ConflictResolver`-Modul mit Offline-Queue gibt es weiterhin nicht — der Tausch feuert synchron online, offline schlägt er mit Fehlermeldung fehl statt sich zu queuen.

11. Haushalt: `HouseholdView` (Profil → „Mitglieder & Einladen“: Mitglieder, Einladungscode per `ShareLink`, beitreten, verlassen) + `JoinHouseholdForm` auch im Onboarding (neues Familienmitglied übernimmt die gemeinsamen Einstellungen). Nach Wechsel `AppEnvironment.refreshAfterHouseholdChange()` (Profil neu laden, lokalen Plan-Cache verwerfen, voll neu syncen). `PlanEntry.totalPortions` (Einkauf/Kosten) und `myPortion` (eigene Makros) kommen vom Server.
12. HealthKit (nur lesend: Gewicht, Größe, Geburtsjahr, Geschlecht) über `HealthService`: „Aus Apple Health übernehmen“ im Survey; danach wird das Gewicht beim App-Start automatisch ins Profil übernommen (ab 0,5 kg Differenz). Begründungstext in `Info.plist` + `Resources/InfoPlist.xcstrings`.
13. Sign in with Apple (`LoginGateView`, Nonce via `AppleNonce`, Prüfung des Credential-Status beim Start). Dev-Login bleibt nur in Debug.

Woche: Plan-Karte antippen öffnet `RecipeDetailView`, nach rechts wischen startet den Kochmodus, nach links tauschen. Mahlzeiten-Anzahl über `PlanSetupForm` (Leerzustand + „Plan neu erstellen“), Slot-Definition in `MealSlots`. `SyncEngine.upsertPlan` löscht ersetzte Einträge ausdrücklich, und `NotificationScheduler` entfernt vor dem Neuplanen alle `start-*`-Erinnerungen — sonst feuern Erinnerungen ersetzter Gerichte weiter.

Fehleranzeige: Der OpenAPI-Runtime verpackt Fehler aus Middlewares/Transport in `ClientError`. Immer `error.userMessage` anzeigen und `error.appError` zum Prüfen von Codes nutzen (nie `catch let e as AppError` oder `localizedDescription`). `ErrorMappingMiddleware` steht in der Middleware-Liste vor `AuthMiddleware`, damit eine 401 zuerst den Refresh auslöst.

Als Nächstes:
14. Google-Login (sobald serverseitig konfiguriert).

Bekannte Vereinfachungen:
- Beim App-Start kann kurz die TabView aufblitzen, bevor das geladene Profil ggf. ins Onboarding umschaltet (kein eigener Lade-Gate gebaut).
- "Plan erstellen" generiert immer nur die aktuelle Woche; Uhrzeiten der Slots sind fest (`priorityMealSlots` in `WeekPlanView`), nur die Anzahl je Tag ist einstellbar. Die Stepper-Werte werden nicht gespeichert.
- Fitness-Survey-Flag und Health-Gewichtsabgleich sind rein lokal (pro Gerät). Hinweise der Plan-Generierung werden nicht persistiert (nur bis zum nächsten Neustart sichtbar).
- Portionen werden nur beim Generieren/Tauschen berechnet — ändert ein Mitglied sein Fitnessziel oder tritt jemand bei, gelten neue Portionen erst nach dem nächsten Neu-Erstellen.
- Konto löschen widerruft die Apple-Anmeldung noch nicht serverseitig (siehe `server/CLAUDE.md`); lokal räumt `AppEnvironment.signOut(deletingAccount:)` Plan-Cache, Erinnerungen, kontobezogene Flags und Favoriten ab.
- Wochentag-Identität (`weekStart`/`date`) ist UTC-verankert, nicht Geräte-Zeitzone; an Tagesgrenzen kann das "heute" um einen Tag abweichen.
- Einkaufsliste summiert Mengen nur bei exakt gleicher Einheit (kein `g`/`el`-Umrechnen wie serverseitig in `vocab.UNIT_CONVERSION`) — dieselbe Zutat kann mit unterschiedlichen Einheiten doppelt auftauchen.
- Abgehakte Einkaufslisten-Posten werden nicht persistiert (nur `@State`, setzt sich beim erneuten Öffnen zurück).

Offen/später: Server-Push, StoreKit-Abo, Widgets/Live Activity für „Jetzt starten“, Fitness-Ausbau (Gewichtsverlauf mit Swift Charts, Aktivität aus Health zur Schätzung des Aktivitätslevels), Thermomix-Sync-Anzeige (echte Cookidoo-Anbindung aktuell nicht umsetzbar, siehe `server/CLAUDE.md` — `cookidoo-api` kann keine Rezepte anlegen/hochladen; lokale Thermomix-Vorzugs-Logik aus den Rezeptschritten wäre ohne Cookidoo-Konto machbar, aber noch nicht gebaut).

## Token sparen

- Generierten OpenAPI-Code, `openapi.json` und `project.pbxproj` nicht komplett lesen. Gezielt mit `grep` arbeiten.
- Für Server-Verhalten erst `server/CLAUDE.md` und `server/api/app/schemas.py` lesen, nicht den ganzen Server.
- Builds und Tests mit `-quiet` bzw. gefilterter Ausgabe (`| xcbeautify`, falls installiert) laufen lassen. Bei Fehlern nur die betroffene Suite erneut ausführen.
