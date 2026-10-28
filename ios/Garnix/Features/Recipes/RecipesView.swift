import SwiftUI
import SwiftData

struct RecipeRoute: Hashable {
    let serverID: String
}

struct RecipesView: View {
    @Query(filter: #Predicate<Recipe> { $0.deletedAt == nil }, sort: \Recipe.title)
    private var recipes: [Recipe]

    @State private var searchText = ""
    @State private var selectedMealType: String?
    @State private var favoritesOnly = false

    private var mealTypes: [String] {
        Set(recipes.flatMap(\.mealTypes)).sorted()
    }

    private var filteredRecipes: [Recipe] {
        recipes.filter { recipe in
            (selectedMealType == nil || recipe.mealTypes.contains(selectedMealType!))
                && (!favoritesOnly || recipe.isFavorite)
                && (searchText.isEmpty || recipe.title.localizedCaseInsensitiveContains(searchText))
        }
    }

    var body: some View {
        Group {
            if recipes.isEmpty {
                ContentUnavailableView(
                    "recipes.empty.title",
                    systemImage: "fork.knife.circle",
                    description: Text("recipes.empty.description")
                )
            } else {
                // Filter-Leiste immer sichtbar (auch bei null Treffern) — sonst gibt's keinen
                // Weg mehr zurück, falls ein aktiver Filter (z. B. "Favoriten") ins Leere läuft.
                List {
                    if !mealTypes.isEmpty {
                        mealTypeFilter
                            .listRowInsets(EdgeInsets())
                            .listRowSeparator(.hidden)
                    }
                    if filteredRecipes.isEmpty {
                        ContentUnavailableView.search(text: searchText)
                            .listRowSeparator(.hidden)
                    } else {
                        ForEach(filteredRecipes) { recipe in
                            NavigationLink(value: RecipeRoute(serverID: recipe.serverID)) {
                                RecipeRow(recipe: recipe)
                            }
                        }
                    }
                }
                .listStyle(.plain)
            }
        }
        .navigationTitle("tab.recipes")
        .searchable(text: $searchText, prompt: Text("recipes.search.prompt"))
        .navigationDestination(for: RecipeRoute.self) { route in
            RecipeDetailView(serverID: route.serverID)
        }
    }

    private var mealTypeFilter: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Spacing.sm) {
                Button {
                    favoritesOnly.toggle()
                } label: {
                    Chip(titleKey: "recipes.filter.favorites", systemImage: "star.fill", isSelected: favoritesOnly)
                }
                .buttonStyle(.plain)
                ForEach(mealTypes, id: \.self) { mealType in
                    Button {
                        selectedMealType = selectedMealType == mealType ? nil : mealType
                    } label: {
                        Chip(title: mealType, isSelected: selectedMealType == mealType)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.xs)
        }
    }
}

private struct RecipeRow: View {
    let recipe: Recipe

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            HStack(spacing: 4) {
                Text(recipe.title)
                    .font(AppFont.sectionTitle)
                if recipe.isFavorite {
                    Image(systemName: "star.fill")
                        .foregroundStyle(.yellow)
                        .font(.caption)
                }
            }
            HStack(spacing: Spacing.sm) {
                Chip(title: "\(recipe.totalMinutes) min", systemImage: "clock")
                if let kcal = recipe.kcal {
                    Chip(title: "\(kcal) kcal", systemImage: "flame")
                }
            }
        }
        .padding(.vertical, Spacing.xs)
    }
}

#Preview {
    NavigationStack {
        RecipesView()
            .modelContainer(for: Recipe.self, inMemory: true)
    }
}
