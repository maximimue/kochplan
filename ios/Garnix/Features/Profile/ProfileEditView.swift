import SwiftUI

struct ProfileEditView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    @State private var supermarket: String?
    @State private var appliances: Set<String>
    @State private var allergens: Set<String>
    @State private var dietTags: Set<String>
    @State private var weeklyBudgetEuros: Int
    @State private var householdSize: Int
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(profile: Components.Schemas.ProfileOut) {
        _supermarket = State(initialValue: profile.supermarket)
        _appliances = State(initialValue: Set(profile.appliances))
        _allergens = State(initialValue: Set(profile.allergens))
        _dietTags = State(initialValue: Set(profile.diet_tags))
        _weeklyBudgetEuros = State(initialValue: (profile.weekly_budget_cents ?? 6000) / 100)
        _householdSize = State(initialValue: profile.household_size)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("onboarding.supermarket.title") {
                    TileGrid(
                        keys: sortedKeys(environment.vocabCache.vocab?.supermarkets.keys.map { $0 }),
                        label: environment.vocabCache.supermarketLabel, icon: { _ in "cart.fill" },
                        isSelected: { supermarket == $0 }, toggle: { supermarket = supermarket == $0 ? nil : $0 }
                    )
                }
                Section("onboarding.appliances.title") {
                    TileGrid(
                        keys: sortedKeys(environment.vocabCache.vocab?.appliances.keys.map { $0 }),
                        label: environment.vocabCache.applianceLabel, icon: applianceIcon,
                        isSelected: { appliances.contains($0) }, toggle: { toggle($0, in: &appliances) }
                    )
                }
                Section("recipes.detail.allergens") {
                    TileGrid(
                        keys: sortedKeys(environment.vocabCache.vocab?.allergens.keys.map { $0 }),
                        label: environment.vocabCache.allergenLabel, icon: { _ in "exclamationmark.triangle" },
                        isSelected: { allergens.contains($0) }, toggle: { toggle($0, in: &allergens) }
                    )
                }
                Section("onboarding.diet.subtitle") {
                    TileGrid(
                        keys: sortedKeys(environment.vocabCache.vocab?.dietTags.keys.map { $0 }),
                        label: environment.vocabCache.dietTagLabel, icon: { _ in "leaf.fill" },
                        isSelected: { dietTags.contains($0) }, toggle: { toggle($0, in: &dietTags) }
                    )
                }
                Section("onboarding.budget.title") {
                    Stepper(value: $weeklyBudgetEuros, in: 10...300, step: 5) {
                        HStack {
                            Text("onboarding.budget.weekly")
                            Spacer()
                            Text(weeklyBudgetEuros, format: .currency(code: "EUR"))
                        }
                    }
                    Stepper(value: $householdSize, in: 1...12) {
                        HStack {
                            Text("onboarding.budget.household")
                            Spacer()
                            Text(householdSize, format: .number)
                        }
                    }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }
            .navigationTitle("profile.edit.button")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("profile.edit.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("profile.edit.save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func sortedKeys(_ keys: [String]?) -> [String] { (keys ?? []).sorted() }

    private func toggle(_ key: String, in set: inout Set<String>) {
        if set.contains(key) { set.remove(key) } else { set.insert(key) }
    }

    private func save() async {
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        do {
            try await environment.profileStore.update(.init(
                supermarket: supermarket,
                weekly_budget_cents: weeklyBudgetEuros * 100,
                household_size: householdSize,
                appliances: Array(appliances),
                allergens: Array(allergens),
                diet_tags: Array(dietTags)
            ))
            dismiss()
        } catch {
            errorMessage = error.userMessage
        }
    }
}
