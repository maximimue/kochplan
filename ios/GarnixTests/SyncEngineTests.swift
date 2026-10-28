import Foundation
import Testing
import SwiftData
import OpenAPIRuntime
@testable import Garnix

@Suite
struct SyncEngineTests {
    @Test
    func deltaSyncUpsertsAndSoftDeletes() async throws {
        let container = try ModelContainer(
            for: Recipe.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let transport = MockClientTransport(responses: [fullSyncResponse, deltaSyncResponse])
        let client = Client(serverURL: URL(string: "https://example.com")!, transport: transport)
        let engine = SyncEngine(modelContainer: container)

        try await engine.syncRecipes(api: client)

        let context = ModelContext(container)
        var all = try context.fetch(FetchDescriptor<Recipe>(sortBy: [SortDescriptor(\.serverID)]))
        #expect(all.count == 2)

        try await engine.syncRecipes(api: client)

        all = try context.fetch(FetchDescriptor<Recipe>(sortBy: [SortDescriptor(\.serverID)]))
        #expect(all.count == 2)

        let pasta = all.first { $0.serverID == "r1" }
        #expect(pasta?.title == "Pasta Update")
        #expect(pasta?.deletedAt == nil)

        let salat = all.first { $0.serverID == "r2" }
        #expect(salat?.deletedAt != nil)

        let paths = await transport.requestPaths
        #expect(paths.count == 2)
        #expect(!paths[0].contains("since="))
        #expect(paths[1].contains("since="))
    }
}

private let fullSyncResponse = Data("""
{
  "server_time": "2024-01-01T00:00:00Z",
  "recipes": [
    {
      "id": "r1", "slug": "pasta", "title": "Pasta",
      "servings": 2, "prep_minutes": 10, "cook_minutes": 15, "passive_minutes": 0, "total_minutes": 25,
      "cost_cents_per_serving": {"standard": 300},
      "appliances": [], "allergens": [], "tags": [], "meal_types": ["abend"],
      "steps": [], "source": "curated", "ingredients": [],
      "updated_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "r2", "slug": "salat", "title": "Salat",
      "servings": 1, "prep_minutes": 5, "cook_minutes": 0, "passive_minutes": 0, "total_minutes": 5,
      "cost_cents_per_serving": {"standard": 150},
      "appliances": [], "allergens": [], "tags": [], "meal_types": ["mittag"],
      "steps": [], "source": "curated", "ingredients": [],
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "deleted_ids": []
}
""".utf8)

private let deltaSyncResponse = Data("""
{
  "server_time": "2024-01-02T00:00:00Z",
  "recipes": [
    {
      "id": "r1", "slug": "pasta", "title": "Pasta Update",
      "servings": 2, "prep_minutes": 10, "cook_minutes": 15, "passive_minutes": 0, "total_minutes": 25,
      "cost_cents_per_serving": {"standard": 310},
      "appliances": [], "allergens": [], "tags": [], "meal_types": ["abend"],
      "steps": [], "source": "curated", "ingredients": [],
      "updated_at": "2024-01-02T00:00:00Z"
    }
  ],
  "deleted_ids": ["r2"]
}
""".utf8)
