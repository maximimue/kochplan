import Foundation
import SwiftData

// ponytail: kein `isDirty` — Rezepte sind reiner Pull-Sync (`GET /v1/recipes/sync`), nie
// lokal editierbar. Feld kommt mit den Plan-Entities (lokale Änderungen, 409/LWW).
@Model
final class Recipe {
    @Attribute(.unique) var serverID: String
    var slug: String
    var title: String
    var summary: String?
    var servings: Int
    var prepMinutes: Int
    var cookMinutes: Int
    var passiveMinutes: Int
    var totalMinutes: Int
    var kcal: Int?
    var proteinG: Double?
    var fatG: Double?
    var carbsG: Double?
    var costCentsPerServing: [String: Int]
    var appliances: [String]
    var allergens: [String]
    var tags: [String]
    var mealTypes: [String]
    /// Freiform-JSON vom Server (`list[dict]`, kein festes Schema) — unverändert durchgereicht.
    var stepsJSON: Data
    var source: String
    var ingredients: [RecipeIngredient]
    var updatedAt: Date
    /// Soft-Delete: Rezept ist aus dem Katalog entfernt, lokale Kopie bleibt bis zum nächsten vollen Sync.
    var deletedAt: Date?
    /// Rein lokal, nicht serverseitig — `RecipeMapper.apply` fasst das Feld bewusst nicht an,
    /// damit ein Re-Sync die Markierung nicht überschreibt.
    /// Default direkt an der Property (nicht nur im `init`-Parameter), sonst scheitert
    /// SwiftDatas automatische Leichtgewichts-Migration bestehender Datenbanken mit
    /// "missing attribute values on mandatory destination attribute".
    var isFavorite: Bool = false

    init(
        serverID: String,
        slug: String = "",
        title: String = "",
        summary: String? = nil,
        servings: Int = 0,
        prepMinutes: Int = 0,
        cookMinutes: Int = 0,
        passiveMinutes: Int = 0,
        totalMinutes: Int = 0,
        kcal: Int? = nil,
        proteinG: Double? = nil,
        fatG: Double? = nil,
        carbsG: Double? = nil,
        costCentsPerServing: [String: Int] = [:],
        appliances: [String] = [],
        allergens: [String] = [],
        tags: [String] = [],
        mealTypes: [String] = [],
        stepsJSON: Data = Data(),
        source: String = "curated",
        ingredients: [RecipeIngredient] = [],
        updatedAt: Date = .distantPast,
        deletedAt: Date? = nil,
        isFavorite: Bool = false
    ) {
        self.serverID = serverID
        self.slug = slug
        self.title = title
        self.summary = summary
        self.servings = servings
        self.prepMinutes = prepMinutes
        self.cookMinutes = cookMinutes
        self.passiveMinutes = passiveMinutes
        self.totalMinutes = totalMinutes
        self.kcal = kcal
        self.proteinG = proteinG
        self.fatG = fatG
        self.carbsG = carbsG
        self.costCentsPerServing = costCentsPerServing
        self.appliances = appliances
        self.allergens = allergens
        self.tags = tags
        self.mealTypes = mealTypes
        self.stepsJSON = stepsJSON
        self.source = source
        self.ingredients = ingredients
        self.updatedAt = updatedAt
        self.deletedAt = deletedAt
        self.isFavorite = isFavorite
    }
}

struct RecipeIngredient: Codable, Hashable {
    var name: String
    var quantity: Double?
    var unit: String?
    var note: String?
}

extension Recipe {
    /// Schritte sind serverseitig `list[dict]` ohne festes Schema — daher tolerant dekodiert,
    /// ein kaputter Schritt darf nicht die ganze Liste leeren.
    struct Step: Decodable, Hashable {
        var text: String
        var minutes: Int?
        var appliance: String?

        private enum CodingKeys: String, CodingKey { case text, minutes, appliance }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            text = (try? c.decode(String.self, forKey: .text)) ?? ""
            minutes = try? c.decode(Int.self, forKey: .minutes)
            appliance = try? c.decode(String.self, forKey: .appliance)
        }
    }

    var decodedSteps: [Step] {
        (try? JSONDecoder().decode([Step].self, from: stepsJSON)) ?? []
    }

    /// Kosten pro Portion in Cent, bevorzugt zum "standard"-Preis-Tier.
    var displayCostCents: Int? {
        costCentsPerServing["standard"] ?? costCentsPerServing.values.first
    }
}
