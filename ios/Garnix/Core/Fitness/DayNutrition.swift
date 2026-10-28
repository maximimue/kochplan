import Foundation

/// Tagessumme für die Tagesübersicht: Makros für die **eigene** Portion (Rezeptwerte sind je
/// Portion × `myPortion`), Kosten für den ganzen Haushalt (wie der Server sie je Eintrag liefert).
struct DayNutrition: Equatable {
    var kcal = 0
    var proteinG = 0.0
    var fatG = 0.0
    var carbsG = 0.0
    var costCents = 0

    static func sum(entries: [PlanEntry], recipes: [Recipe]) -> DayNutrition {
        let recipesByID = Dictionary(recipes.map { ($0.serverID, $0) }, uniquingKeysWith: { first, _ in first })
        var total = DayNutrition()
        for entry in entries {
            total.costCents += entry.costCents ?? 0
            guard let recipeID = entry.recipeServerID, let recipe = recipesByID[recipeID] else { continue }
            let portion = entry.myPortion
            total.kcal += Int((Double(recipe.kcal ?? 0) * portion).rounded())
            total.proteinG += (recipe.proteinG ?? 0) * portion
            total.fatG += (recipe.fatG ?? 0) * portion
            total.carbsG += (recipe.carbsG ?? 0) * portion
        }
        return total
    }
}
