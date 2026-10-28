import SwiftUI
import SwiftData
import OSLog
import OpenAPIRuntime

private let logger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "Garnix", category: "weekplan")

struct WeekPlanView: View {
    @Environment(AppEnvironment.self) private var environment
    @Query(filter: #Predicate<MealPlan> { $0.deletedAt == nil }, sort: \MealPlan.weekStart)
    private var plans: [MealPlan]
    @Query(filter: #Predicate<Recipe> { $0.deletedAt == nil })
    private var allRecipes: [Recipe]

    @State private var selectedDate: Date = WeekPlanView.utcCalendar.startOfDay(for: Date())
    @State private var isGenerating = false
    @State private var errorMessage: String?
    @State private var swappingEntry: PlanEntry?
    @State private var openedRecipe: RecipeRoute?
    @State private var cookingRecipe: Recipe?
    @State private var isShowingShoppingList = false
    @State private var isShowingRegenerate = false
    @State private var mealCounts = Array(repeating: MealSlots.maxPerDay, count: 7)
    /// Hinweise aus der letzten Generierung (Budget, Wiederholungen, Fitnessziel) — nur Anzeige, nicht persistiert.
    @State private var planWarnings: [String] = []

    private var profile: Components.Schemas.ProfileOut? { environment.profileStore.profile }

    private var weekStart: Date { Self.mondayOfWeek(containing: Date()) }
    private var weekDates: [Date] { (0..<7).compactMap { Self.utcCalendar.date(byAdding: .day, value: $0, to: weekStart) } }
    private var currentPlan: MealPlan? { plans.first { $0.weekStart == weekStart } }
    private var selectedEntries: [PlanEntry] {
        (currentPlan?.entries ?? [])
            .filter { Self.utcCalendar.isDate($0.date, inSameDayAs: selectedDate) }
            .sorted { ($0.startAt ?? .distantFuture) < ($1.startAt ?? .distantFuture) }
    }

    var body: some View {
        Group {
            if let currentPlan {
                planContent
                    .toolbar {
                        Button {
                            isShowingShoppingList = true
                        } label: {
                            Image(systemName: "cart")
                        }
                        .accessibilityLabel(Text("shoppinglist.title"))
                    }
                    .sheet(isPresented: $isShowingShoppingList) {
                        ShoppingListView(plan: currentPlan)
                    }
                    .sheet(isPresented: $isShowingRegenerate) {
                        regenerateSheet
                    }
            } else {
                PlanSetupForm(
                    mealCounts: $mealCounts, weekDates: weekDates, isGenerating: isGenerating,
                    errorMessage: errorMessage, showsIntro: true
                ) {
                    Task { await generatePlan() }
                }
            }
        }
        .navigationTitle("tab.week")
        .navigationDestination(item: $openedRecipe) { route in
            RecipeDetailView(serverID: route.serverID)
        }
        .fullScreenCover(item: $cookingRecipe) { recipe in
            CookingModeView(recipe: recipe)
        }
        .onChange(of: profile?.recommended_meals_per_day, initial: true) { _, recommended in
            if let recommended { mealCounts = Array(repeating: recommended, count: 7) }
        }
        .sheet(item: $swappingEntry) { entry in
            RecipePickerView { recipe in
                Task { await performSwap(entry: entry, to: recipe) }
            }
        }
    }

    private var planContent: some View {
        VStack(spacing: 0) {
            dayScroller
            if let errorMessage {
                Text(errorMessage).foregroundStyle(.red).padding(.horizontal, Spacing.md)
            }
            if !planWarnings.isEmpty {
                warningsBanner
            }
            List {
                if selectedEntries.isEmpty {
                    ContentUnavailableView("weekplan.day.empty", systemImage: "fork.knife")
                        .listRowSeparator(.hidden)
                }
                ForEach(selectedEntries, id: \.serverID) { entry in
                    entryRow(entry)
                }
                if !selectedEntries.isEmpty {
                    daySummaryRow
                        .listRowSeparator(.hidden)
                        .listRowBackground(Color.clear)
                        .listRowInsets(EdgeInsets(top: Spacing.xs, leading: Spacing.md, bottom: Spacing.xs, trailing: Spacing.md))
                }
                Button {
                    isShowingRegenerate = true
                } label: {
                    Label("weekplan.regenerate.action", systemImage: "arrow.clockwise")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: Spacing.sm, leading: Spacing.md, bottom: Spacing.lg, trailing: Spacing.md))
            }
            .listStyle(.plain)
        }
    }

    /// Antippen öffnet das Rezept; nach rechts wischen = direkt kochen, nach links = tauschen.
    private func entryRow(_ entry: PlanEntry) -> some View {
        let recipe = allRecipes.first { $0.serverID == entry.recipeServerID }
        return Button {
            if let id = entry.recipeServerID { openedRecipe = RecipeRoute(serverID: id) }
        } label: {
            PlanEntryCard(entry: entry, recipe: recipe, mealLabel: environment.vocabCache.mealTypeLabel(entry.meal))
        }
        .buttonStyle(.plain)
        .listRowSeparator(.hidden)
        .listRowBackground(Color.clear)
        .listRowInsets(EdgeInsets(top: Spacing.xs, leading: Spacing.md, bottom: Spacing.xs, trailing: Spacing.md))
        .swipeActions(edge: .leading) {
            if let recipe, !recipe.decodedSteps.isEmpty {
                Button {
                    cookingRecipe = recipe
                } label: {
                    Label("weekplan.cook.action", systemImage: "play.fill")
                }
                .tint(.green)
            }
        }
        .swipeActions(edge: .trailing) {
            Button {
                swappingEntry = entry
            } label: {
                Label("weekplan.swap.action", systemImage: "arrow.triangle.2.circlepath")
            }
            .tint(.accentColor)
        }
    }

    private var warningsBanner: some View {
        HStack(alignment: .top, spacing: Spacing.sm) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: Spacing.xs) {
                ForEach(planWarnings, id: \.self) { Text(verbatim: $0).font(.footnote) }
            }
            Spacer(minLength: 0)
            Button {
                planWarnings = []
            } label: {
                Image(systemName: "xmark").font(.footnote)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("weekplan.warnings.dismiss"))
        }
        .padding(Spacing.md)
        .background(AppColor.cardBackground, in: RoundedRectangle(cornerRadius: Radius.md))
        .padding(.horizontal, Spacing.md)
        .padding(.bottom, Spacing.sm)
    }

    private var daySummaryRow: some View {
        let summary = DayNutrition.sum(entries: selectedEntries, recipes: allRecipes)
        return VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("weekplan.summary.title").font(AppFont.sectionTitle)
            if let targetKcal = profile?.target_kcal, let targetProtein = profile?.target_protein_g {
                targetProgress("weekplan.summary.kcal", value: Double(summary.kcal), target: Double(targetKcal), unit: "kcal")
                targetProgress("weekplan.summary.protein", value: summary.proteinG, target: Double(targetProtein), unit: "g")
            }
            HStack(spacing: Spacing.sm) {
                if profile?.target_kcal == nil {
                    Chip(title: "\(summary.kcal) kcal", systemImage: "flame")
                    Chip(title: "P \(summary.proteinG.formatted(.number.precision(.fractionLength(0)))) g", systemImage: "bolt.fill")
                }
                Chip(title: "F \(summary.fatG.formatted(.number.precision(.fractionLength(0)))) g", systemImage: "drop.fill")
                Chip(title: "K \(summary.carbsG.formatted(.number.precision(.fractionLength(0)))) g", systemImage: "leaf.fill")
                Chip(title: (Double(summary.costCents) / 100).formatted(.currency(code: "EUR")), systemImage: "eurosign.circle")
            }
        }
        .padding(Spacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppColor.cardBackground, in: RoundedRectangle(cornerRadius: Radius.lg))
    }

    private func targetProgress(_ title: LocalizedStringKey, value: Double, target: Double, unit: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(title).font(.subheadline)
                Spacer()
                Text(verbatim: "\(value.formatted(.number.precision(.fractionLength(0)))) / \(target.formatted(.number.precision(.fractionLength(0)))) \(unit)")
                    .font(AppFont.metric)
                    .monospacedDigit()
            }
            ProgressView(value: min(value, target), total: max(target, 1))
                .tint(abs(value - target) / max(target, 1) <= 0.15 ? .green : .orange)
        }
    }

    private func performSwap(entry: PlanEntry, to newRecipe: Recipe) async {
        guard let plan = currentPlan else { return }
        let entries = plan.entries.map { planEntry in
            PlanMapper.planEntryIn(
                from: planEntry,
                overridingRecipeID: planEntry.serverID == entry.serverID ? newRecipe.serverID : nil
            )
        }
        do {
            let success = try await environment.syncEngine.putPlan(
                weekStart: PlanMapper.format(date: plan.weekStart),
                clientUpdatedAt: Date(),
                entries: entries,
                api: environment.apiClient.client
            )
            errorMessage = success ? nil : String(localized: "weekplan.swap.conflict")
        } catch {
            errorMessage = error.userMessage
        }
    }

    private var regenerateSheet: some View {
        NavigationStack {
            PlanSetupForm(mealCounts: $mealCounts, weekDates: weekDates, isGenerating: isGenerating, errorMessage: errorMessage) {
                Task {
                    await generatePlan()
                    if errorMessage == nil { isShowingRegenerate = false }
                }
            }
            .navigationTitle("weekplan.regenerate.action")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("profile.edit.cancel") { isShowingRegenerate = false }
                }
            }
        }
    }

    private var dayScroller: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Spacing.sm) {
                ForEach(weekDates, id: \.self) { day in
                    let isSelected = Self.utcCalendar.isDate(day, inSameDayAs: selectedDate)
                    Button {
                        selectedDate = day
                    } label: {
                        VStack(spacing: 2) {
                            Text(day, format: .dateTime.weekday(.abbreviated))
                            Text(day, format: .dateTime.day())
                                .font(.headline)
                        }
                        .frame(width: 48, height: 56)
                        .background(
                            isSelected ? Color.accentColor.opacity(0.2) : AppColor.cardBackground,
                            in: RoundedRectangle(cornerRadius: Radius.md)
                        )
                        .foregroundStyle(isSelected ? Color.accentColor : .primary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(Spacing.md)
        }
    }

    private func generatePlan() async {
        logger.notice("generatePlan tapped, weekStart=\(PlanMapper.format(date: weekStart), privacy: .public)")
        isGenerating = true
        errorMessage = nil
        defer { isGenerating = false }

        let slots = zip(weekDates, mealCounts).flatMap { day, count in
            MealSlots.slots(count: count).map { slot in
                Components.Schemas.SlotIn(date: PlanMapper.format(date: day), meal: slot.meal, eat_at: slot.eatAt)
            }
        }
        do {
            let response = try await environment.apiClient.client.generatePlan(.init(
                body: .json(.init(week_start: PlanMapper.format(date: weekStart), slots: slots, use_ai: true))
            ))
            guard case let .ok(ok) = response, case let .json(plan) = ok.body else {
                logger.error("generatePlan: unexpected response shape: \(String(describing: response), privacy: .public)")
                errorMessage = String(localized: "weekplan.generate.failed")
                return
            }
            logger.notice("generatePlan: got plan with \(plan.entries.count) entries")
            planWarnings = (plan.warnings ?? []).compactMap { $0.additionalProperties.value["message"] as? String }
            try await environment.syncEngine.upsertPlan(plan)
        } catch {
            logger.error("generatePlan failed: \(String(describing: error), privacy: .public)")
            errorMessage = error.userMessage
        }
    }

    fileprivate static let utcCalendar: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar
    }()

    private static func mondayOfWeek(containing date: Date) -> Date {
        var calendar = utcCalendar
        calendar.firstWeekday = 2
        let startOfToday = calendar.startOfDay(for: date)
        let weekday = calendar.component(.weekday, from: startOfToday)
        let daysFromMonday = (weekday + 5) % 7
        return calendar.date(byAdding: .day, value: -daysFromMonday, to: startOfToday)!
    }
}

private struct PlanEntryCard: View {
    let entry: PlanEntry
    let recipe: Recipe?
    let mealLabel: String

    var body: some View {
        HStack(alignment: .center, spacing: Spacing.sm) {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                HStack(spacing: Spacing.sm) {
                    Text(verbatim: mealLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if let startAt = entry.startAt {
                        HStack(spacing: 4) {
                            Text("weekplan.startAt.label")
                            Text(startAt, format: .dateTime.hour().minute()).fontWeight(.bold)
                        }
                        .font(.subheadline)
                        .foregroundStyle(Color.accentColor)
                    }
                }
                Text(entry.recipeTitle ?? mealLabel)
                    .font(AppFont.sectionTitle)
                    .multilineTextAlignment(.leading)
                HStack(spacing: Spacing.sm) {
                    if let minutes = entry.totalMinutes {
                        Chip(title: "\(minutes) min", systemImage: "clock")
                    }
                    if let cents = entry.costCents {
                        Chip(title: (Double(cents) / 100).formatted(.currency(code: "EUR")), systemImage: "eurosign.circle")
                    }
                    if let kcal = recipe?.kcal {
                        Chip(title: "\(Int((Double(kcal) * entry.myPortion).rounded())) kcal", systemImage: "flame")
                    }
                    if entry.myPortion != 1 {
                        Chip(title: "× \(entry.myPortion.formatted(.number.precision(.fractionLength(0...2))))", systemImage: "fork.knife")
                            .accessibilityLabel(Text("weekplan.portion.accessibility \(entry.myPortion.formatted())"))
                    }
                }
            }
            Spacer(minLength: 0)
            if entry.recipeServerID != nil {
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(Spacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppColor.cardBackground, in: RoundedRectangle(cornerRadius: Radius.lg))
        .contentShape(RoundedRectangle(cornerRadius: Radius.lg))
    }
}
