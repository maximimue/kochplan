import SwiftUI
import SwiftData

struct ShoppingListView: View {
    let plan: MealPlan
    @Environment(\.dismiss) private var dismiss
    @Query(filter: #Predicate<Recipe> { $0.deletedAt == nil })
    private var recipes: [Recipe]
    @State private var checkedItems: Set<String> = []

    private var items: [ShoppingListItem] {
        ShoppingListBuilder.build(for: plan, recipes: recipes)
    }

    var body: some View {
        NavigationStack {
            Group {
                if items.isEmpty {
                    ContentUnavailableView("shoppinglist.empty.title", systemImage: "cart")
                } else {
                    List(items) { item in
                        Button {
                            toggle(item.id)
                        } label: {
                            row(for: item)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .navigationTitle("shoppinglist.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("profile.edit.cancel") { dismiss() }
                }
            }
        }
    }

    private func row(for item: ShoppingListItem) -> some View {
        let isChecked = checkedItems.contains(item.id)
        return HStack {
            Image(systemName: isChecked ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(isChecked ? Color.accentColor : .secondary)
            Text(item.name)
                .strikethrough(isChecked)
                .foregroundStyle(isChecked ? .secondary : .primary)
            Spacer()
            if let quantity = item.quantity {
                Text(verbatim: "\(quantity.formatted()) \(item.unit ?? "")")
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func toggle(_ id: String) {
        if checkedItems.contains(id) { checkedItems.remove(id) } else { checkedItems.insert(id) }
    }
}
