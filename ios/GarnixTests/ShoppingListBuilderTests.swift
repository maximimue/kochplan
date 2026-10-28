import Foundation
import Testing
@testable import Garnix

@Suite
struct ShoppingListBuilderTests {
    @Test
    func aggregatesAndScalesAcrossEntries() {
        let pasta = Recipe(
            serverID: "r1", servings: 2,
            ingredients: [
                RecipeIngredient(name: "Nudeln", quantity: 200, unit: "g"),
                RecipeIngredient(name: "Salz", quantity: nil, unit: nil),
            ]
        )
        let salad = Recipe(
            serverID: "r2", servings: 1,
            ingredients: [
                RecipeIngredient(name: "nudeln", quantity: 100, unit: "g"),
                RecipeIngredient(name: "Tomate", quantity: 2, unit: "stk"),
            ]
        )

        let plan = MealPlan(serverID: "p1", weekStart: Date())
        let entry1 = PlanEntry(serverID: "e1", date: Date(), meal: "abend", totalPortions: 4, recipeServerID: "r1")
        let entry2 = PlanEntry(serverID: "e2", date: Date(), meal: "mittag", totalPortions: 2, recipeServerID: "r2")
        plan.entries = [entry1, entry2]

        let items = ShoppingListBuilder.build(for: plan, recipes: [pasta, salad])

        // Nudeln: r1 skaliert 4/2=2x200g=400g, r2 skaliert 2/1=2x100g=200g -> 600g gesamt.
        let nudeln = items.first { $0.name.lowercased() == "nudeln" }
        #expect(nudeln?.quantity == 600)
        #expect(nudeln?.unit == "g")

        let salz = items.first { $0.name == "Salz" }
        #expect(salz?.quantity == nil)

        let tomate = items.first { $0.name == "Tomate" }
        #expect(tomate?.quantity == 4)
    }

    @Test
    func ignoresEntriesWithoutMatchingRecipe() {
        let plan = MealPlan(serverID: "p1", weekStart: Date())
        plan.entries = [PlanEntry(serverID: "e1", date: Date(), meal: "abend", recipeServerID: "unknown")]

        let items = ShoppingListBuilder.build(for: plan, recipes: [])
        #expect(items.isEmpty)
    }
}
