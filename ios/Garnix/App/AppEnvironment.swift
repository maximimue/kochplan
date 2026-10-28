import Foundation
import SwiftData

@MainActor
@Observable
final class AppEnvironment {
    let authService: AuthService
    let apiClient: APIClient
    let syncEngine: SyncEngine
    let vocabCache: VocabCache
    let profileStore: ProfileStore
    let healthService = HealthService()

    init(baseURL: URL, modelContainer: ModelContainer) {
        let authService = AuthService(baseURL: baseURL)
        self.authService = authService
        let apiClient = APIClient(baseURL: baseURL, authService: authService)
        self.apiClient = apiClient
        self.syncEngine = SyncEngine(modelContainer: modelContainer)
        self.vocabCache = VocabCache(api: apiClient.client)
        self.profileStore = ProfileStore(api: apiClient.client)
    }

    /// Lokale Daten gehören immer genau einem Konto. Meldet sich ein anderes an (oder läuft diese Version
    /// zum ersten Mal), werden Plan-Cache und kontobezogene Flags verworfen — sonst zeigte die Woche den
    /// alten Plan des vorherigen Kontos statt des eigenen.
    func discardDataOfOtherAccount() async {
        guard let userID = profileStore.profile?.id else { return }
        let key = "account.userID"
        guard UserDefaults.standard.string(forKey: key) != userID else { return }
        try? await syncEngine.clearPlans()
        UserDefaults.standard.removeObject(forKey: "fitness.surveyHandled")
        healthService.isWeightSyncEnabled = false
        UserDefaults.standard.set(userID, forKey: key)
    }

    /// Abmelden bzw. nach dem Konto-Löschen: keine Daten des Kontos auf dem Gerät zurücklassen
    /// (Plan-Cache und damit Erinnerungen, kontobezogene Flags; beim Löschen auch Favoriten).
    func signOut(deletingAccount: Bool = false) async {
        try? await syncEngine.clearPlans()
        if deletingAccount {
            try? await syncEngine.clearFavorites()
        }
        UserDefaults.standard.removeObject(forKey: "fitness.surveyHandled")
        healthService.isWeightSyncEnabled = false
        profileStore.reset()
        authService.logout()
    }

    /// Nach Beitreten/Verlassen: gemeinsame Einstellungen und Pläne kommen jetzt aus einem anderen Haushalt.
    func refreshAfterHouseholdChange() async throws {
        try await profileStore.refresh()
        try await syncEngine.resyncPlans(api: apiClient.client)
    }

    /// Neueres Gewicht aus Health ins Profil übernehmen, damit Tagesbedarf und Portionen mitwandern.
    func syncWeightFromHealth() async throws {
        guard healthService.isWeightSyncEnabled, let profile = profileStore.profile, profile.fitness_goal != nil else { return }
        let healthKg = await healthService.readBodyData().weightKg
        guard HealthService.shouldUpdateWeight(profileKg: profile.weight_kg, healthKg: healthKg), let healthKg else { return }
        try await profileStore.update(.init(weight_kg: healthKg))
    }

    convenience init(modelContainer: ModelContainer) {
        guard let urlString = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
              let baseURL = URL(string: urlString) else {
            fatalError("API_BASE_URL fehlt in Info.plist — Config/*.xcconfig im Info-Tab des Targets verdrahten.")
        }
        self.init(baseURL: baseURL, modelContainer: modelContainer)
    }
}
