import Foundation
import Testing
@testable import Garnix

@Suite
@MainActor
struct VocabCacheTests {
    @Test
    func refreshDecodesAndCachesVocab() async throws {
        defer { UserDefaults.standard.removeObject(forKey: "meta.vocab") }

        let transport = MockClientTransport(responses: [vocabResponse])
        let client = Client(serverURL: URL(string: "https://example.com")!, transport: transport)
        let cache = VocabCache(api: client)

        try await cache.refresh()

        #expect(cache.applianceLabel("herd") == "Herd")
        #expect(cache.applianceLabel("unbekannt") == "unbekannt")
        #expect(cache.allergenLabel("gluten") == "Gluten")
        #expect(cache.dietTagLabel("vegan") == "Vegan")
        #expect(cache.supermarketLabel("rewe") == "REWE")
    }

    @Test
    func cachedVocabSurvivesNewInstance() async throws {
        defer { UserDefaults.standard.removeObject(forKey: "meta.vocab") }

        let transport = MockClientTransport(responses: [vocabResponse])
        let client = Client(serverURL: URL(string: "https://example.com")!, transport: transport)
        let first = VocabCache(api: client)
        try await first.refresh()

        let second = VocabCache(api: client)
        #expect(second.applianceLabel("herd") == "Herd")
    }
}

private let vocabResponse = Data("""
{
  "appliances": {"herd": "Herd", "backofen": "Backofen"},
  "allergens": {"gluten": "Gluten"},
  "diet_tags": {"vegan": "Vegan"},
  "meal_types": {"abend": "Abend"},
  "supermarkets": {"rewe": {"label": "REWE", "price_tier": "standard"}}
}
""".utf8)
