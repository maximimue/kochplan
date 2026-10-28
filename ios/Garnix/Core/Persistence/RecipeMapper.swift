import Foundation

enum RecipeMapper {
    static func apply(_ dto: Components.Schemas.RecipeOut, to recipe: Recipe) throws {
        recipe.slug = dto.slug
        recipe.title = dto.title
        recipe.summary = dto.summary
        recipe.servings = dto.servings
        recipe.prepMinutes = dto.prep_minutes
        recipe.cookMinutes = dto.cook_minutes
        recipe.passiveMinutes = dto.passive_minutes
        recipe.totalMinutes = dto.total_minutes
        recipe.kcal = dto.kcal
        recipe.proteinG = dto.protein_g
        recipe.fatG = dto.fat_g
        recipe.carbsG = dto.carbs_g
        recipe.costCentsPerServing = dto.cost_cents_per_serving.additionalProperties
        recipe.appliances = dto.appliances
        recipe.allergens = dto.allergens
        recipe.tags = dto.tags
        recipe.mealTypes = dto.meal_types
        recipe.stepsJSON = try JSONEncoder().encode(dto.steps)
        recipe.source = dto.source
        recipe.ingredients = dto.ingredients.map {
            RecipeIngredient(name: $0.name, quantity: $0.quantity, unit: $0.unit, note: $0.note)
        }
        recipe.updatedAt = dto.updated_at
        recipe.deletedAt = nil
    }
}
