import SwiftUI
import SwiftData
import Charts

struct RecipeDetailView: View {
    @Query private var recipes: [Recipe]
    @State private var servingsOverride: Int?
    @State private var isCooking = false

    init(serverID: String) {
        _recipes = Query(filter: #Predicate<Recipe> { $0.serverID == serverID })
    }

    private var recipe: Recipe? { recipes.first }

    var body: some View {
        if let recipe {
            ScrollView {
                VStack(alignment: .leading, spacing: Spacing.lg) {
                    hero(recipe)
                    if !recipe.decodedSteps.isEmpty {
                        Button {
                            isCooking = true
                        } label: {
                            Label("cooking.start", systemImage: "play.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .fullScreenCover(isPresented: $isCooking) {
                            CookingModeView(recipe: recipe)
                        }
                    }
                    metrics(recipe)
                    if hasMacros(recipe) {
                        macrosChart(recipe)
                    }
                    if !recipe.allergens.isEmpty {
                        allergens(recipe)
                    }
                    ingredients(recipe)
                    steps(recipe)
                }
                .padding(Spacing.md)
            }
            .navigationTitle(recipe.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                Button {
                    recipe.isFavorite.toggle()
                } label: {
                    Image(systemName: recipe.isFavorite ? "star.fill" : "star")
                }
                .accessibilityLabel(Text("recipes.favorite.toggle"))
            }
        } else {
            ContentUnavailableView("recipes.empty.title", systemImage: "fork.knife.circle")
        }
    }

    private func hero(_ recipe: Recipe) -> some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(
                colors: [Color.accentColor.opacity(0.6), Color.accentColor.opacity(0.2)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            .frame(height: 160)
            .clipShape(RoundedRectangle(cornerRadius: Radius.lg))

            VStack(alignment: .leading, spacing: 2) {
                Text(recipe.title).font(.title2.bold())
                if let summary = recipe.summary {
                    Text(summary).font(.subheadline)
                }
            }
            .foregroundStyle(.white)
            .padding(Spacing.md)
        }
    }

    private func metrics(_ recipe: Recipe) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Spacing.sm) {
                Chip(title: "\(recipe.totalMinutes) min", systemImage: "clock")
                if let cents = recipe.displayCostCents {
                    Chip(title: (Double(cents) / 100).formatted(.currency(code: "EUR")), systemImage: "eurosign.circle")
                }
                if let kcal = recipe.kcal {
                    Chip(title: "\(kcal) kcal", systemImage: "flame")
                }
                ForEach(recipe.appliances, id: \.self) { appliance in
                    Chip(title: appliance, systemImage: "fork.knife")
                }
            }
        }
    }

    private func hasMacros(_ recipe: Recipe) -> Bool {
        recipe.proteinG != nil || recipe.fatG != nil || recipe.carbsG != nil
    }

    private func macrosChart(_ recipe: Recipe) -> some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            Text("recipes.detail.macros").font(AppFont.sectionTitle)
            Chart {
                if let protein = recipe.proteinG {
                    BarMark(x: .value("Makro", "Protein"), y: .value("g", protein))
                }
                if let fat = recipe.fatG {
                    BarMark(x: .value("Makro", "Fett"), y: .value("g", fat))
                }
                if let carbs = recipe.carbsG {
                    BarMark(x: .value("Makro", "Kohlenhydrate"), y: .value("g", carbs))
                }
            }
            .frame(height: 140)
        }
    }

    private func allergens(_ recipe: Recipe) -> some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            Text("recipes.detail.allergens").font(AppFont.sectionTitle)
            HStack(spacing: Spacing.sm) {
                ForEach(recipe.allergens, id: \.self) { allergen in
                    Chip(title: allergen, systemImage: "exclamationmark.triangle")
                }
            }
        }
    }

    private func ingredients(_ recipe: Recipe) -> some View {
        let servings = servingsOverride ?? recipe.servings
        let scale = Double(servings) / Double(max(recipe.servings, 1))

        return VStack(alignment: .leading, spacing: Spacing.xs) {
            Stepper(value: Binding(get: { servings }, set: { servingsOverride = $0 }), in: 1...12) {
                HStack {
                    Text("recipes.detail.servings")
                    Spacer()
                    Text(servings, format: .number)
                }
            }
            ForEach(recipe.ingredients, id: \.self) { ingredient in
                HStack {
                    Text(ingredient.name)
                    Spacer()
                    if let quantity = ingredient.quantity {
                        Text("\((quantity * scale).formatted()) \(ingredient.unit ?? "")")
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private func steps(_ recipe: Recipe) -> some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("recipes.detail.steps").font(AppFont.sectionTitle)
            ForEach(Array(recipe.decodedSteps.enumerated()), id: \.offset) { index, step in
                HStack(alignment: .top, spacing: Spacing.sm) {
                    Text("\(index + 1).").fontWeight(.semibold)
                    Text(step.text)
                }
            }
        }
    }
}

#Preview {
    NavigationStack {
        RecipeDetailView(serverID: "preview")
            .modelContainer(for: Recipe.self, inMemory: true)
    }
}
