import Foundation

struct VocabOut: Codable, Hashable {
    var appliances: [String: String]
    var allergens: [String: String]
    var dietTags: [String: String]
    var mealTypes: [String: String]
    var supermarkets: [String: SupermarketEntry]
    // Optional, damit ältere Server-Antworten und der lokale Cache weiter dekodieren.
    var fitnessGoals: [String: String]?
    var sexes: [String: String]?
    var activityLevels: [String: String]?

    enum CodingKeys: String, CodingKey {
        case appliances, allergens, supermarkets, sexes
        case dietTags = "diet_tags"
        case mealTypes = "meal_types"
        case fitnessGoals = "fitness_goals"
        case activityLevels = "activity_levels"
    }
}

struct SupermarketEntry: Codable, Hashable {
    var label: String
    var priceTier: String

    enum CodingKeys: String, CodingKey {
        case label
        case priceTier = "price_tier"
    }
}

/// Vokabular-Labels aus `/v1/meta/vocab`, lokal gecacht. Unbekannte Keys fallen auf den
/// Key selbst zurück statt zu crashen.
///
/// ponytail: `/v1/meta/vocab` liefert kein typisiertes Response-Schema (FastAPI-Endpunkt ohne
/// `response_model`), der generierte Client gibt daher nur `OpenAPIValueContainer` zurück —
/// hier einmalig nachdekodiert statt mit eigenem `URLSession`-Call. Würde ein `response_model`
/// am Server ergänzt, entfiele der Umweg.
@MainActor
@Observable
final class VocabCache {
    private(set) var vocab: VocabOut?
    private let api: any APIProtocol

    init(api: any APIProtocol) {
        self.api = api
        self.vocab = Self.loadCached()
    }

    func refresh() async throws {
        let response = try await api.getVocab(.init())
        guard case let .ok(ok) = response, case let .json(container) = ok.body else {
            throw AppError(code: "vocab_failed", message: "Vokabular konnte nicht geladen werden.")
        }
        let data = try JSONEncoder().encode(container)
        let decoded = try JSONDecoder().decode(VocabOut.self, from: data)
        vocab = decoded
        UserDefaults.standard.set(data, forKey: Self.cacheKey)
    }

    func applianceLabel(_ key: String) -> String { vocab?.appliances[key] ?? key }
    func allergenLabel(_ key: String) -> String { vocab?.allergens[key] ?? key }
    func dietTagLabel(_ key: String) -> String { vocab?.dietTags[key] ?? key }
    func supermarketLabel(_ key: String) -> String { vocab?.supermarkets[key]?.label ?? key }
    func mealTypeLabel(_ key: String) -> String { vocab?.mealTypes[key] ?? key }
    func fitnessGoalLabel(_ key: String) -> String { vocab?.fitnessGoals?[key] ?? key }
    func sexLabel(_ key: String) -> String { vocab?.sexes?[key] ?? key }
    func activityLevelLabel(_ key: String) -> String { vocab?.activityLevels?[key] ?? key }

    private static let cacheKey = "meta.vocab"

    private static func loadCached() -> VocabOut? {
        guard let data = UserDefaults.standard.data(forKey: cacheKey) else { return nil }
        return try? JSONDecoder().decode(VocabOut.self, from: data)
    }
}

/// SF-Symbol je Gerät — unbekannte Keys bekommen ein neutrales Fallback-Symbol.
func applianceIcon(_ key: String) -> String {
    switch key {
    case "herd": "flame"
    case "backofen": "flame.fill"
    case "mikrowelle": "waveform"
    case "thermomix": "gearshape.fill"
    case "airfryer": "wind"
    case "wasserkocher": "drop.fill"
    case "mixer": "tornado"
    case "dampfgarer": "humidity.fill"
    case "slowcooker": "clock.fill"
    case "grill": "flame.circle.fill"
    default: "fork.knife"
    }
}
