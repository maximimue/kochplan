import Foundation

struct ShoppingListItem: Identifiable, Hashable {
    let id: String
    let name: String
    var quantity: Double?
    let unit: String?
}

/// Einkaufsliste aus bereits lokal synchronisierten Daten (Plan + Rezept-Zutaten) berechnet —
/// kein eigener Server-Endpunkt nötig.
///
/// ponytail: Mengen werden nur bei exakt gleicher Einheit summiert (kein `g`/`el`-Umrechnen wie
/// serverseitig in `UNIT_CONVERSION`) — dieselbe Zutat kann mit unterschiedlichen Einheiten
/// doppelt auftauchen. Umrechnung nachziehen, falls das in der Praxis stört.
enum ShoppingListBuilder {
    static func build(for plan: MealPlan, recipes: [Recipe]) -> [ShoppingListItem] {
        let recipesByID = Dictionary(uniqueKeysWithValues: recipes.map { ($0.serverID, $0) })
        var items: [String: ShoppingListItem] = [:]

        for entry in plan.entries {
            guard let recipeID = entry.recipeServerID, let recipe = recipesByID[recipeID] else { continue }
            let scale = entry.totalPortions / Double(max(recipe.servings, 1))
            for ingredient in recipe.ingredients {
                let unitKey = ingredient.unit?.lowercased() ?? ""
                let key = "\(ingredient.name.lowercased())|\(unitKey)"
                let scaledQuantity = ingredient.quantity.map { $0 * scale }
                if var existing = items[key] {
                    if let addQty = scaledQuantity {
                        existing.quantity = (existing.quantity ?? 0) + addQty
                    }
                    items[key] = existing
                } else {
                    items[key] = ShoppingListItem(id: key, name: ingredient.name, quantity: scaledQuantity, unit: ingredient.unit)
                }
            }
        }
        return items.values.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }
}
