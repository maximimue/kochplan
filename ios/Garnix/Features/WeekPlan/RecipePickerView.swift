import SwiftUI
import SwiftData

struct RecipePickerView: View {
    let onSelect: (Recipe) -> Void
    @Environment(\.dismiss) private var dismiss
    @Query(filter: #Predicate<Recipe> { $0.deletedAt == nil })
    private var recipes: [Recipe]
    @State private var searchText = ""

    private var filtered: [Recipe] {
        let base = searchText.isEmpty
            ? recipes
            : recipes.filter { $0.title.localizedCaseInsensitiveContains(searchText) }
        let sorted = base.sorted { $0.title.localizedCompare($1.title) == .orderedAscending }
        return sorted.filter(\.isFavorite) + sorted.filter { !$0.isFavorite }
    }

    var body: some View {
        NavigationStack {
            List(filtered) { recipe in
                Button {
                    onSelect(recipe)
                    dismiss()
                } label: {
                    row(for: recipe)
                }
                .buttonStyle(.plain)
            }
            .searchable(text: $searchText, prompt: Text("recipes.search.prompt"))
            .navigationTitle("weekplan.swap.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("profile.edit.cancel") { dismiss() }
                }
            }
        }
    }

    private func row(for recipe: Recipe) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(recipe.title).font(AppFont.sectionTitle)
                Text(verbatim: "\(recipe.totalMinutes) min")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if recipe.isFavorite {
                Image(systemName: "star.fill").foregroundStyle(.yellow)
            }
        }
    }
}
