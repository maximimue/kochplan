import Foundation
import Testing
import SwiftData
import OpenAPIRuntime
@testable import Garnix

@Suite
struct PlanSyncTests {
    @Test
    func deltaSyncUpsertsAndSoftDeletes() async throws {
        let container = try ModelContainer(
            for: Recipe.self, MealPlan.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let transport = MockClientTransport(responses: [fullListResponse, deltaResponse])
        let client = Client(serverURL: URL(string: "https://example.com")!, transport: transport)
        let engine = SyncEngine(modelContainer: container)

        try await engine.syncPlans(api: client)

        let context = ModelContext(container)
        var all = try context.fetch(FetchDescriptor<MealPlan>(sortBy: [SortDescriptor(\.serverID)]))
        #expect(all.count == 2)

        try await engine.syncPlans(api: client)

        all = try context.fetch(FetchDescriptor<MealPlan>(sortBy: [SortDescriptor(\.serverID)]))
        #expect(all.count == 2)

        let p1 = all.first { $0.serverID == "p1" }
        #expect(p1?.totalCostCents == 500)
        #expect(p1?.deletedAt == nil)

        let p2 = all.first { $0.serverID == "p2" }
        #expect(p2?.deletedAt != nil)

        let paths = await transport.requestPaths
        #expect(paths.count == 2)
        #expect(!paths[0].contains("since="))
        #expect(paths[1].contains("since="))
    }
}

private let fullListResponse = Data("""
[
  {
    "id": "p1", "week_start": "2026-06-08", "entries": [],
    "total_cost_cents": 0, "over_budget": false,
    "updated_at": "2026-06-01T00:00:00Z", "client_updated_at": "2026-06-01T00:00:00Z"
  },
  {
    "id": "p2", "week_start": "2026-06-15", "entries": [],
    "total_cost_cents": 0, "over_budget": false,
    "updated_at": "2026-06-02T00:00:00Z", "client_updated_at": "2026-06-02T00:00:00Z"
  }
]
""".utf8)

extension PlanSyncTests {
    /// Regression: ersetzte Einträge blieben als Waisen liegen und wurden weiter als Erinnerung eingeplant.
    @Test
    func regeneratedPlanLeavesNoOrphanEntries() async throws {
        let container = try ModelContainer(
            for: Recipe.self, MealPlan.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let transport = MockClientTransport(responses: [planWithEntries(["e1", "e2"]), planWithEntries(["e3"])])
        let client = Client(serverURL: URL(string: "https://example.com")!, transport: transport)
        let engine = SyncEngine(modelContainer: container)

        try await engine.syncPlans(api: client)
        try await engine.syncPlans(api: client)

        let entries = try ModelContext(container).fetch(FetchDescriptor<PlanEntry>())
        #expect(entries.map(\.serverID) == ["e3"])
        #expect(entries.first?.myPortion == 1.25)
    }
}

private func planWithEntries(_ ids: [String]) -> Data {
    let entries = ids.map { id in
        """
        {"id": "\(id)", "date": "2026-06-08", "meal": "abend", "eat_at": "18:30:00", "total_portions": 2.25,
         "my_portion": 1.25, "recipe_id": null, "recipe_title": null, "total_minutes": null,
         "start_at": "2026-06-08T17:00:00Z", "cost_cents": null}
        """
    }.joined(separator: ",")
    return Data("""
    [{"id": "p1", "week_start": "2026-06-08", "entries": [\(entries)], "total_cost_cents": 0, "over_budget": false,
      "updated_at": "2026-06-01T00:00:0\(ids.count)Z", "client_updated_at": "2026-06-01T00:00:00Z"}]
    """.utf8)
}

private let deltaResponse = Data("""
[
  {
    "id": "p1", "week_start": "2026-06-08", "entries": [],
    "total_cost_cents": 500, "over_budget": false,
    "updated_at": "2026-06-03T00:00:00Z", "client_updated_at": "2026-06-03T00:00:00Z"
  },
  {
    "id": "p2", "week_start": "2026-06-15", "entries": [],
    "total_cost_cents": 0, "over_budget": false,
    "updated_at": "2026-06-04T00:00:00Z", "client_updated_at": "2026-06-04T00:00:00Z", "deleted": true
  }
]
""".utf8)
