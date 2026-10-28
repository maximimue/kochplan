import Foundation
import Testing
@testable import Garnix

@Suite
struct DayNutritionTests {
    @Test
    func macrosUseOwnPortionAndCostIsHousehold() {
        let curry = Recipe(serverID: "r1", servings: 2, kcal: 600, proteinG: 25, fatG: 20, carbsG: 70)
        let oats = Recipe(serverID: "r2", servings: 1, kcal: 400, proteinG: 12, fatG: 10, carbsG: 60)
        // Eigene Portion 1,5 bzw. 1,0 — Gesamtportionen und Rezept-Portionen spielen für die eigenen Makros keine Rolle.
        let entries = [
            PlanEntry(serverID: "e1", date: Date(), meal: "abend", totalPortions: 2.25, myPortion: 1.5, recipeServerID: "r1", costCents: 250),
            PlanEntry(serverID: "e2", date: Date(), meal: "fruehstueck", totalPortions: 2, recipeServerID: "r2", costCents: 90),
            PlanEntry(serverID: "e3", date: Date(), meal: "snack", recipeServerID: "fehlt", costCents: 50),
        ]

        let sum = DayNutrition.sum(entries: entries, recipes: [curry, oats])

        #expect(sum.kcal == 1300)
        #expect(sum.proteinG == 49.5)
        #expect(sum.fatG == 40)
        #expect(sum.carbsG == 165)
        #expect(sum.costCents == 390)
    }
}
