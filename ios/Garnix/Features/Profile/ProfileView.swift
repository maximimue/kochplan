import SwiftUI
import SwiftData

struct ProfileView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var isEditing = false
    @State private var isEditingFitness = false
    @State private var isConfirmingDelete = false
    @State private var errorMessage: String?

    // RootView zeigt diesen Tab erst, wenn `authService.isAuthenticated` true ist —
    // kein "nicht angemeldet"-Zustand hier nötig (das übernimmt `LoginGateView`).
    var body: some View {
        if let profile = environment.profileStore.profile {
            List {
                Section {
                    if let name = profile.display_name {
                        Text(name).font(AppFont.sectionTitle)
                    }
                    if let email = profile.email {
                        Text(email).foregroundStyle(.secondary)
                    }
                }
                Section("profile.section.household") {
                    NavigationLink("household.manage") { HouseholdView() }
                    LabeledContent(
                        "profile.field.supermarket",
                        value: profile.supermarket.map(environment.vocabCache.supermarketLabel) ?? "—"
                    )
                    LabeledContent(
                        "profile.field.budget",
                        value: profile.weekly_budget_cents.map { (Double($0) / 100).formatted(.currency(code: "EUR")) } ?? "—"
                    )
                    LabeledContent("profile.field.household", value: "\(profile.household_size)")
                    if !profile.appliances.isEmpty {
                        LabeledContent(
                            "profile.field.appliances",
                            value: profile.appliances.map(environment.vocabCache.applianceLabel).joined(separator: ", ")
                        )
                    }
                }
                Section("profile.section.personal") {
                    LabeledContent(
                        "profile.field.allergens",
                        value: profile.allergens.isEmpty ? "—" : profile.allergens.map(environment.vocabCache.allergenLabel).joined(separator: ", ")
                    )
                    LabeledContent(
                        "profile.field.diet",
                        value: profile.diet_tags.isEmpty ? "—" : profile.diet_tags.map(environment.vocabCache.dietTagLabel).joined(separator: ", ")
                    )
                }
                Section("profile.section.fitness") {
                    if let goal = profile.fitness_goal, let kcal = profile.target_kcal {
                        LabeledContent("fitness.field.goal", value: environment.vocabCache.fitnessGoalLabel(goal))
                        LabeledContent("fitness.field.kcal", value: "\(kcal.formatted()) kcal")
                        FitnessTargetsView(profile: profile)
                        if profile.fitness_deficit_capped == true {
                            Text("fitness.capped.note").font(.footnote).foregroundStyle(.orange)
                        }
                    } else {
                        Text("fitness.none.hint").foregroundStyle(.secondary)
                    }
                    Button("fitness.edit.button") { isEditingFitness = true }
                }
                Section("profile.section.sync") {
                    LabeledContent(
                        "profile.field.lastSync",
                        value: SyncEngine.lastRecipeSyncDate?.formatted(date: .abbreviated, time: .shortened) ?? "—"
                    )
                }
                Section {
                    Button("profile.edit.button") { isEditing = true }
                    Button("profile.logout.button", role: .destructive) { Task { await environment.signOut() } }
                    Button("profile.delete.button", role: .destructive) { isConfirmingDelete = true }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }
            .navigationTitle("tab.profile")
            .sheet(isPresented: $isEditing) {
                ProfileEditView(profile: profile)
            }
            .sheet(isPresented: $isEditingFitness) {
                FitnessSurveyView(profile: profile)
            }
            .confirmationDialog("profile.delete.confirm", isPresented: $isConfirmingDelete, titleVisibility: .visible) {
                Button("profile.delete.button", role: .destructive) {
                    Task { await deleteAccount() }
                }
            } message: {
                Text("profile.delete.message")
            }
        } else {
            ProgressView()
                .navigationTitle("tab.profile")
                .task { try? await environment.profileStore.refresh() }
        }
    }

    private func deleteAccount() async {
        do {
            try await environment.profileStore.delete()
            await environment.signOut(deletingAccount: true)
        } catch {
            errorMessage = error.userMessage
        }
    }
}

#Preview {
    let container = try! ModelContainer(for: Recipe.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true))
    NavigationStack {
        ProfileView()
            .environment(AppEnvironment(baseURL: URL(string: "http://localhost:8000")!, modelContainer: container))
    }
}
