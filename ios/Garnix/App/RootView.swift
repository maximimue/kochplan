import SwiftUI
import SwiftData
import OSLog

private let logger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "Garnix", category: "sync")

struct RootView: View {
    @Environment(AppEnvironment.self) private var environment
    @Query(filter: #Predicate<PlanEntry> { $0.startAt != nil })
    private var scheduledEntries: [PlanEntry]
    /// Survey nur einmal automatisch zeigen (gesetzt beim Schließen, egal ob mit Ziel oder übersprungen);
    /// danach jederzeit über das Profil erreichbar.
    // ponytail: rein lokal statt Server-Flag — genügt bei einem Gerät, sonst Feld im Profil ergänzen.
    @AppStorage("fitness.surveyHandled") private var fitnessSurveyHandled = false
    @State private var isShowingFitnessSurvey = false

    var body: some View {
        Group {
            if !environment.authService.isAuthenticated {
                LoginGateView()
            } else if let profile = environment.profileStore.profile, profile.supermarket == nil {
                OnboardingView()
            } else {
                TabView {
                    Tab("tab.week", systemImage: "calendar") {
                        NavigationStack {
                            WeekPlanView()
                        }
                    }
                    Tab("tab.recipes", systemImage: "fork.knife") {
                        NavigationStack {
                            RecipesView()
                        }
                    }
                    Tab("tab.profile", systemImage: "person.crop.circle") {
                        NavigationStack {
                            ProfileView()
                        }
                    }
                }
            }
        }
        .onChange(of: environment.authService.isAuthenticated, initial: true) { _, isAuthenticated in
            logger.notice("isAuthenticated changed to \(isAuthenticated)")
            guard isAuthenticated else { return }
            Task {
                await NotificationScheduler.requestAuthorization()
                await run("profileStore.refresh") { try await environment.profileStore.refresh() }
                await environment.discardDataOfOtherAccount()
                presentFitnessSurveyIfNeeded()
                await run("health.syncWeight") { try await environment.syncWeightFromHealth() }
                await run("vocabCache.refresh") { try await environment.vocabCache.refresh() }
                await run("syncEngine.syncRecipes") { try await environment.syncEngine.syncRecipes(api: environment.apiClient.client) }
                await run("syncEngine.syncPlans") { try await environment.syncEngine.syncPlans(api: environment.apiClient.client) }
                logger.notice("post-login sync finished, profile=\(environment.profileStore.profile != nil)")
            }
        }
        .task {
            logger.notice("RootView appeared, isAuthenticated=\(environment.authService.isAuthenticated)")
            await environment.authService.checkAppleCredentialState()
        }
        // Auslöser: Abschluss des Onboardings (supermarket wird gesetzt) bzw. Login (nach dem Konto-Abgleich).
        // Bewusst kein abgeleitetes isPresented: sonst schlösse sich das Cover, sobald das Ziel
        // gespeichert ist — noch vor dem Ergebnis-Schritt.
        .onChange(of: environment.profileStore.profile?.supermarket) { _, _ in
            presentFitnessSurveyIfNeeded()
        }
        .fullScreenCover(isPresented: $isShowingFitnessSurvey, onDismiss: { fitnessSurveyHandled = true }) {
            FitnessSurveyView(profile: environment.profileStore.profile)
        }
        .onChange(of: scheduledEntries, initial: true) { _, entries in
            Task {
                let notificationEntries = entries
                    .filter { $0.plan != nil && $0.plan?.deletedAt == nil }
                    .compactMap { entry in
                        entry.startAt.map { NotificationScheduler.Entry(id: entry.serverID, startAt: $0, recipeTitle: entry.recipeTitle) }
                    }
                await NotificationScheduler.reschedule(for: notificationEntries)
            }
        }
    }

    private func presentFitnessSurveyIfNeeded() {
        guard let profile = environment.profileStore.profile else { return }
        if profile.supermarket != nil && profile.fitness_goal == nil && !fitnessSurveyHandled {
            isShowingFitnessSurvey = true
        }
    }

    private func run(_ label: String, _ operation: () async throws -> Void) async {
        do {
            try await operation()
            logger.notice("\(label) succeeded")
        } catch {
            logger.error("\(label) failed: \(String(describing: error))")
        }
    }
}
