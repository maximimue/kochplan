import Foundation
import Testing
@testable import Garnix

@Suite
struct RecipeMapperTests {
    @Test
    func mapsAllFields() throws {
        let dto = Components.Schemas.RecipeOut(
            id: "r-1", slug: "pasta", title: "Pasta", summary: "Schnell",
            servings: 2, prep_minutes: 10, cook_minutes: 15, passive_minutes: 0, total_minutes: 25,
            kcal: 650, protein_g: 20, fat_g: 18, carbs_g: 70,
            cost_cents_per_serving: .init(additionalProperties: ["standard": 320]),
            appliances: ["herd"], allergens: ["gluten"], tags: ["schnell"], meal_types: ["abend"],
            steps: [.init()],
            source: "curated",
            ingredients: [.init(name: "Nudeln", quantity: 200, unit: "g", note: nil)],
            updated_at: Date(timeIntervalSince1970: 1_700_000_000)
        )

        let recipe = Recipe(serverID: dto.id)
        try RecipeMapper.apply(dto, to: recipe)

        #expect(recipe.serverID == "r-1")
        #expect(recipe.title == "Pasta")
        #expect(recipe.summary == "Schnell")
        #expect(recipe.kcal == 650)
        #expect(recipe.proteinG == 20)
        #expect(recipe.costCentsPerServing["standard"] == 320)
        #expect(recipe.appliances == ["herd"])
        #expect(recipe.ingredients.count == 1)
        #expect(recipe.ingredients.first?.name == "Nudeln")
        #expect(recipe.ingredients.first?.quantity == 200)
        #expect(recipe.ingredients.first?.unit == "g")
        #expect(recipe.deletedAt == nil)
    }

    @Test
    func mapsMissingOptionalsAsNil() throws {
        let dto = Components.Schemas.RecipeOut(
            id: "r-2", slug: "salat", title: "Salat", summary: nil,
            servings: 1, prep_minutes: 5, cook_minutes: 0, passive_minutes: 0, total_minutes: 5,
            kcal: nil, protein_g: nil, fat_g: nil, carbs_g: nil,
            cost_cents_per_serving: .init(),
            appliances: [], allergens: [], tags: [], meal_types: [],
            steps: [], source: "curated", ingredients: [],
            updated_at: Date(timeIntervalSince1970: 1_700_000_000)
        )

        let recipe = Recipe(serverID: dto.id)
        try RecipeMapper.apply(dto, to: recipe)

        #expect(recipe.summary == nil)
        #expect(recipe.kcal == nil)
        #expect(recipe.proteinG == nil)
        #expect(recipe.ingredients.isEmpty)
    }

    @Test
    func reApplyingClearsSoftDelete() throws {
        let recipe = Recipe(serverID: "r-3")
        recipe.deletedAt = Date()

        let dto = Components.Schemas.RecipeOut(
            id: "r-3", slug: "suppe", title: "Suppe", summary: nil,
            servings: 2, prep_minutes: 5, cook_minutes: 20, passive_minutes: 0, total_minutes: 25,
            kcal: nil, protein_g: nil, fat_g: nil, carbs_g: nil,
            cost_cents_per_serving: .init(),
            appliances: [], allergens: [], tags: [], meal_types: [],
            steps: [], source: "curated", ingredients: [],
            updated_at: Date(timeIntervalSince1970: 1_700_000_000)
        )
        try RecipeMapper.apply(dto, to: recipe)

        #expect(recipe.deletedAt == nil)
    }
}
