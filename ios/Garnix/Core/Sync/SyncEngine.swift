import Foundation
import SwiftData

@ModelActor
actor SyncEngine {
    /// Delta-Sync: ohne vorherigen Lauf kompletter Abgleich, danach inkrementell über `since`.
    func syncRecipes(api: any APIProtocol) async throws {
        let since = lastRecipeSyncDate()
        let response = try await api.syncRecipes(.init(query: .init(since: since)))
        guard case let .ok(ok) = response, case let .json(syncOut) = ok.body else {
            throw AppError(code: "sync_failed", message: "Rezept-Sync fehlgeschlagen.")
        }

        for dto in syncOut.recipes {
            let recipe = try fetchRecipe(serverID: dto.id) ?? Recipe(serverID: dto.id)
            try RecipeMapper.apply(dto, to: recipe)
            modelContext.insert(recipe)
        }
        for deletedID in syncOut.deleted_ids {
            try fetchRecipe(serverID: deletedID)?.deletedAt = syncOut.server_time
        }
        try modelContext.save()
        setLastRecipeSyncDate(syncOut.server_time)
    }

    /// Delta-Sync für Pläne: pull-only (kein 409/LWW-Upload in dieser Phase, siehe `MealPlan`).
    /// `since` ist das späteste gesehene `updated_at`, nicht die aktuelle Uhrzeit — der Server
    /// liefert kein eigenes `server_time` für Pläne wie bei Rezepten.
    func syncPlans(api: any APIProtocol) async throws {
        let since = lastPlanSyncDate()
        let response = try await api.listPlans(.init(query: .init(since: since)))
        guard case let .ok(ok) = response, case let .json(plans) = ok.body else {
            throw AppError(code: "sync_failed", message: "Plan-Sync fehlgeschlagen.")
        }
        for dto in plans {
            try upsertPlan(dto)
        }
        if let maxUpdatedAt = plans.map(\.updated_at).max() {
            setLastPlanSyncDate(maxUpdatedAt)
        }
    }

    /// Nach einem Haushaltswechsel gelten andere Pläne: lokalen Cache verwerfen und neu vollständig synchronisieren.
    func resyncPlans(api: any APIProtocol) async throws {
        try clearPlans()
        try await syncPlans(api: api)
    }

    /// Lokale Pläne samt Sync-Stand löschen (Abmelden, Konto löschen, Haushaltswechsel).
    func clearPlans() throws {
        try modelContext.delete(model: PlanEntry.self)
        try modelContext.delete(model: MealPlan.self)
        try modelContext.save()
        UserDefaults.standard.removeObject(forKey: Keys.lastPlanSync)
    }

    /// Favoriten sind rein lokal und persönlich — beim Konto-Löschen mit entfernen.
    func clearFavorites() throws {
        for recipe in try modelContext.fetch(FetchDescriptor<Recipe>(predicate: #Predicate { $0.isFavorite })) {
            recipe.isFavorite = false
        }
        try modelContext.save()
    }

    func upsertPlan(_ dto: Components.Schemas.PlanOut) throws {
        let plan = try fetchPlan(serverID: dto.id) ?? MealPlan(serverID: dto.id, weekStart: .distantPast)
        let previousEntries = plan.entries
        try PlanMapper.apply(dto, to: plan)
        modelContext.insert(plan)
        // Aus `plan.entries` entfernte Einträge löscht SwiftData nicht selbst (Cascade greift nur beim
        // Löschen des Plans) — ohne Aufräumen blieben sie liegen und würden weiter erinnert.
        let keptIDs = Set(plan.entries.map(\.serverID))
        for entry in previousEntries where !keptIDs.contains(entry.serverID) {
            modelContext.delete(entry)
        }
        try modelContext.save()
        // Waisen aus App-Versionen vor dieser Bereinigung (wirkt erst auf dem gespeicherten Stand).
        try modelContext.delete(model: PlanEntry.self, where: #Predicate { $0.plan == nil })
        try modelContext.save()
    }

    /// Ersetzt die komplette Eintragsliste der Woche serverseitig (z. B. beim Tauschen eines
    /// Gerichts). Bei 409 (Last-Write-Wins) wird die Serverversion übernommen.
    /// - Returns: `true` bei Erfolg, `false` wenn ein Konflikt aufgetreten ist (Serverversion
    ///   wurde trotzdem übernommen, der Aufrufer sollte das dezent anzeigen).
    func putPlan(
        weekStart: String, clientUpdatedAt: Date, entries: [Components.Schemas.PlanEntryIn], api: any APIProtocol
    ) async throws -> Bool {
        do {
            let response = try await api.upsertPlan(.init(
                path: .init(week_start: weekStart),
                body: .json(.init(client_updated_at: clientUpdatedAt, entries: entries))
            ))
            guard case let .ok(ok) = response, case let .json(plan) = ok.body else {
                throw AppError(code: "plan_update_failed", message: "Plan konnte nicht gespeichert werden.")
            }
            try upsertPlan(plan)
            return true
        } catch {
            guard let appError = error.appError, appError.code == "sync_conflict" else { throw error }
            if let data = appError.rawResponseData,
               let conflict = try? JSONDecoder.garnix.decode(ConflictPayload.self, from: data) {
                try upsertPlan(conflict.server_version)
            }
            return false
        }
    }

    private func fetchRecipe(serverID: String) throws -> Recipe? {
        var descriptor = FetchDescriptor<Recipe>(predicate: #Predicate { $0.serverID == serverID })
        descriptor.fetchLimit = 1
        return try modelContext.fetch(descriptor).first
    }

    private func fetchPlan(serverID: String) throws -> MealPlan? {
        var descriptor = FetchDescriptor<MealPlan>(predicate: #Predicate { $0.serverID == serverID })
        descriptor.fetchLimit = 1
        return try modelContext.fetch(descriptor).first
    }

    private func lastRecipeSyncDate() -> Date? {
        UserDefaults.standard.object(forKey: Keys.lastRecipeSync) as? Date
    }

    private func setLastRecipeSyncDate(_ date: Date) {
        UserDefaults.standard.set(date, forKey: Keys.lastRecipeSync)
    }

    private func lastPlanSyncDate() -> Date? {
        UserDefaults.standard.object(forKey: Keys.lastPlanSync) as? Date
    }

    private func setLastPlanSyncDate(_ date: Date) {
        UserDefaults.standard.set(date, forKey: Keys.lastPlanSync)
    }

    private enum Keys {
        static let lastRecipeSync = "sync.lastRecipeSync"
        static let lastPlanSync = "sync.lastPlanSync"
    }
}

extension SyncEngine {
    /// Für die Sync-Status-Anzeige im Profil — liest denselben UserDefaults-Key wie die Actor-interne Logik.
    nonisolated static var lastRecipeSyncDate: Date? {
        UserDefaults.standard.object(forKey: Keys.lastRecipeSync) as? Date
    }
}

private struct ConflictPayload: Decodable {
    let server_version: Components.Schemas.PlanOut
}
