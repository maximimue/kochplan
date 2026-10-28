import SwiftUI

struct OnboardingView: View {
    @Environment(AppEnvironment.self) private var environment

    @State private var step = 0
    @State private var supermarket: String?
    @State private var appliances: Set<String> = []
    @State private var allergens: Set<String> = []
    @State private var dietTags: Set<String> = []
    @State private var weeklyBudgetEuros = 60
    @State private var householdSize = 2
    @State private var isSaving = false
    @State private var errorMessage: String?

    private let totalSteps = 4

    var body: some View {
        NavigationStack {
            VStack(spacing: Spacing.lg) {
                ProgressView(value: Double(step + 1), total: Double(totalSteps))
                    .padding(.horizontal, Spacing.md)

                ScrollView {
                    content.padding(Spacing.md)
                }

                if let errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                        .padding(.horizontal, Spacing.md)
                }

                HStack {
                    if step > 0 {
                        Button("onboarding.back") { step -= 1 }
                    }
                    Spacer()
                    Button(step == totalSteps - 1 ? "onboarding.finish" : "onboarding.next") {
                        if step == totalSteps - 1 {
                            Task { await finish() }
                        } else {
                            step += 1
                        }
                    }
                    .disabled(isSaving)
                }
                .padding(.horizontal, Spacing.md)
                .padding(.bottom, Spacing.md)
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .task { try? await environment.vocabCache.refresh() }
        }
    }

    private var title: LocalizedStringKey {
        switch step {
        case 0: "onboarding.supermarket.title"
        case 1: "onboarding.appliances.title"
        case 2: "onboarding.allergens.title"
        default: "onboarding.budget.title"
        }
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case 0: supermarketStep
        case 1: applianceStep
        case 2: allergensStep
        default: budgetStep
        }
    }

    private var supermarketKeys: [String] { sortedKeys(environment.vocabCache.vocab?.supermarkets.keys.map { $0 }) }
    private var applianceKeys: [String] { sortedKeys(environment.vocabCache.vocab?.appliances.keys.map { $0 }) }
    private var allergenKeys: [String] { sortedKeys(environment.vocabCache.vocab?.allergens.keys.map { $0 }) }
    private var dietTagKeys: [String] { sortedKeys(environment.vocabCache.vocab?.dietTags.keys.map { $0 }) }

    private func sortedKeys(_ keys: [String]?) -> [String] { (keys ?? []).sorted() }

    private var supermarketStep: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            // Beitreten übernimmt Supermarkt, Budget und Geräte des Haushalts — RootView verlässt
            // das Onboarding dann von selbst, weil `supermarket` gesetzt ist.
            DisclosureGroup("onboarding.join.title") {
                JoinHouseholdForm(requiresConfirmation: false)
                    .padding(.top, Spacing.sm)
            }
            .padding(Spacing.md)
            .background(AppColor.cardBackground, in: RoundedRectangle(cornerRadius: Radius.md))
            TileGrid(
                keys: supermarketKeys, label: environment.vocabCache.supermarketLabel, icon: { _ in "cart.fill" },
                isSelected: { supermarket == $0 }, toggle: { supermarket = supermarket == $0 ? nil : $0 }
            )
        }
    }

    private var applianceStep: some View {
        TileGrid(
            keys: applianceKeys, label: environment.vocabCache.applianceLabel, icon: applianceIcon,
            isSelected: { appliances.contains($0) }, toggle: { toggle($0, in: &appliances) }
        )
    }

    private var allergensStep: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text("onboarding.allergens.subtitle").font(AppFont.sectionTitle)
                TileGrid(
                    keys: allergenKeys, label: environment.vocabCache.allergenLabel, icon: { _ in "exclamationmark.triangle" },
                    isSelected: { allergens.contains($0) }, toggle: { toggle($0, in: &allergens) }
                )
            }
            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text("onboarding.diet.subtitle").font(AppFont.sectionTitle)
                TileGrid(
                    keys: dietTagKeys, label: environment.vocabCache.dietTagLabel, icon: { _ in "leaf.fill" },
                    isSelected: { dietTags.contains($0) }, toggle: { toggle($0, in: &dietTags) }
                )
            }
        }
    }

    private var budgetStep: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
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
    }

    private func toggle(_ key: String, in set: inout Set<String>) {
        if set.contains(key) { set.remove(key) } else { set.insert(key) }
    }

    private func finish() async {
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
        } catch {
            errorMessage = error.userMessage
        }
    }
}
