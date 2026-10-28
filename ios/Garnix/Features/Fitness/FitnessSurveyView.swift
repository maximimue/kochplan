import SwiftUI

/// Fitness-Survey: Ziel → Körperdaten → Aktivität → Ergebnis. Speichert per `PATCH /v1/me`;
/// Tagesbedarf und Makro-Ziele berechnet der Server (`services/fitness.py`).
struct FitnessSurveyView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.dismiss) private var dismiss

    private enum Step: Int, CaseIterable { case goal, body, activity, result }

    // Anzeige-Reihenfolge der Vokabular-Keys; Labels kommen aus `/v1/meta/vocab`.
    private static let goalKeys = ["abnehmen", "halten", "aufbauen"]
    private static let sexKeys = ["weiblich", "maennlich", "divers"]
    private static let activityKeys = ["sitzend", "leicht", "maessig", "aktiv", "sehr_aktiv"]
    // Spiegeln die Server-Validierung (`ProfilePatch`), damit Fehler schon hier auffallen.
    private static let ageRange = 18...100
    private static let heightRange = 120...230
    private static let weightRange = 35.0...300.0

    @State private var step: Step = .goal
    @State private var goal: String?
    @State private var sex: String?
    @State private var birthYear: Int?
    @State private var heightCm: Int?
    @State private var weightKg: Double?
    @State private var activityLevel: String?
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(profile: Components.Schemas.ProfileOut?) {
        _goal = State(initialValue: profile?.fitness_goal)
        _sex = State(initialValue: profile?.sex)
        _birthYear = State(initialValue: profile?.birth_year)
        _heightCm = State(initialValue: profile?.height_cm)
        _weightKg = State(initialValue: profile?.weight_kg)
        _activityLevel = State(initialValue: profile?.activity_level)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: Spacing.lg) {
                ProgressView(value: Double(step.rawValue + 1), total: Double(Step.allCases.count))
                    .padding(.horizontal, Spacing.md)
                ScrollView {
                    content.padding(Spacing.md)
                }
                if let errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                        .padding(.horizontal, Spacing.md)
                }
                navigationButtons
                    .padding(.horizontal, Spacing.md)
                    .padding(.bottom, Spacing.md)
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if step != .result {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("fitness.survey.skip") { dismiss() }
                    }
                }
            }
            .task { try? await environment.vocabCache.refresh() }
        }
    }

    private var title: LocalizedStringKey {
        switch step {
        case .goal: "fitness.survey.title.goal"
        case .body: "fitness.survey.title.body"
        case .activity: "fitness.survey.title.activity"
        case .result: "fitness.survey.title.result"
        }
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .goal: goalStep
        case .body: bodyStep
        case .activity: activityStep
        case .result: resultStep
        }
    }

    // MARK: Schritte

    private var goalStep: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            Text("fitness.goal.subtitle").foregroundStyle(.secondary)
            TileGrid(
                keys: Self.goalKeys, label: environment.vocabCache.fitnessGoalLabel, icon: goalIcon,
                isSelected: { goal == $0 }, toggle: { goal = $0 }
            )
            Button("fitness.goal.none") {
                Task { await clearGoal() }
            }
            .disabled(isSaving)
        }
    }

    private var bodyStep: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            if environment.healthService.isAvailable {
                Button {
                    Task { await importFromHealth() }
                } label: {
                    Label("fitness.health.import", systemImage: "heart.text.square")
                }
                .buttonStyle(.bordered)
                if environment.healthService.isWeightSyncEnabled {
                    Text("fitness.health.syncNote").font(.footnote).foregroundStyle(.secondary)
                }
            }
            Picker("fitness.body.sex", selection: $sex) {
                ForEach(Self.sexKeys, id: \.self) { key in
                    Text(verbatim: environment.vocabCache.sexLabel(key)).tag(Optional(key))
                }
            }
            .pickerStyle(.segmented)

            numberField("fitness.body.birthYear", value: $birthYear, format: .number.grouping(.never))
            numberField("fitness.body.height", value: $heightCm, format: .number)
            LabeledContent("fitness.body.weight") {
                TextField("fitness.body.weight", value: $weightKg, format: .number.precision(.fractionLength(0...1)))
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
            }
            if hasBodyInput && !isBodyValid {
                Text("fitness.body.invalid").font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private func numberField(_ title: LocalizedStringKey, value: Binding<Int?>, format: IntegerFormatStyle<Int>) -> some View {
        LabeledContent(title) {
            TextField(title, value: value, format: format)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
        }
    }

    private var activityStep: some View {
        VStack(spacing: Spacing.sm) {
            ForEach(Self.activityKeys, id: \.self) { key in
                let isSelected = activityLevel == key
                Button {
                    activityLevel = key
                } label: {
                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        Text(verbatim: environment.vocabCache.activityLevelLabel(key)).font(AppFont.sectionTitle)
                        // Key erst als String bauen: ein interpoliertes Literal würde zum Format-Key
                        // "fitness.activity.%@.hint", den es im Katalog nicht gibt.
                        let hintKey = "fitness.activity.\(key).hint"
                        Text(LocalizedStringKey(hintKey))
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Spacing.md)
                    .background(
                        isSelected ? Color.accentColor.opacity(0.15) : AppColor.cardBackground,
                        in: RoundedRectangle(cornerRadius: Radius.md)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: Radius.md)
                            .strokeBorder(isSelected ? Color.accentColor : .clear, lineWidth: 2)
                    )
                }
                .buttonStyle(.plain)
            }
        }
    }

    @ViewBuilder
    private var resultStep: some View {
        if let profile = environment.profileStore.profile, let kcal = profile.target_kcal {
            VStack(alignment: .leading, spacing: Spacing.lg) {
                if let goal = profile.fitness_goal {
                    Text(verbatim: environment.vocabCache.fitnessGoalLabel(goal)).font(.headline)
                }
                Text(verbatim: "\(kcal.formatted()) kcal")
                    .font(.system(.largeTitle, design: .rounded).weight(.bold))
                FitnessTargetsView(profile: profile)
                if profile.fitness_deficit_capped == true {
                    Text("fitness.capped.note").font(.footnote).foregroundStyle(.orange)
                }
                Text("fitness.disclaimer").font(.footnote).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            ContentUnavailableView("fitness.result.unavailable", systemImage: "exclamationmark.triangle")
        }
    }

    // MARK: Navigation

    private var navigationButtons: some View {
        HStack {
            if step != .goal && step != .result {
                Button("onboarding.back") { step = Step(rawValue: step.rawValue - 1) ?? .goal }
            }
            Spacer()
            switch step {
            case .result:
                Button("fitness.result.done") { dismiss() }
                    .buttonStyle(.borderedProminent)
            case .activity:
                Button {
                    Task { await save() }
                } label: {
                    if isSaving { ProgressView() } else { Text("onboarding.finish") }
                }
                .buttonStyle(.borderedProminent)
                .disabled(activityLevel == nil || isSaving)
            default:
                Button("onboarding.next") { step = Step(rawValue: step.rawValue + 1) ?? .result }
                    .buttonStyle(.borderedProminent)
                    .disabled(!canAdvance)
            }
        }
    }

    private var canAdvance: Bool {
        switch step {
        case .goal: goal != nil
        case .body: sex != nil && isBodyValid
        case .activity, .result: true
        }
    }

    private var hasBodyInput: Bool { birthYear != nil || heightCm != nil || weightKg != nil }

    private var isBodyValid: Bool {
        guard let birthYear, let heightCm, let weightKg else { return false }
        let age = Calendar.current.component(.year, from: Date()) - birthYear
        return Self.ageRange.contains(age) && Self.heightRange.contains(heightCm) && Self.weightRange.contains(weightKg)
    }

    private func goalIcon(_ key: String) -> String {
        switch key {
        case "abnehmen": "arrow.down.right.circle"
        case "aufbauen": "dumbbell"
        default: "equal.circle"
        }
    }

    // MARK: Speichern

    /// Übernimmt vorhandene Health-Werte; was Health nicht liefert, bleibt wie eingegeben.
    private func importFromHealth() async {
        errorMessage = nil
        do {
            try await environment.healthService.requestAuthorization()
        } catch {
            errorMessage = error.userMessage
            return
        }
        let data = await environment.healthService.readBodyData()
        guard data != HealthService.BodyData() else {
            errorMessage = String(localized: "fitness.health.empty")
            return
        }
        weightKg = data.weightKg ?? weightKg
        heightCm = data.heightCm ?? heightCm
        birthYear = data.birthYear ?? birthYear
        sex = data.sex ?? sex
        environment.healthService.isWeightSyncEnabled = data.weightKg != nil
    }

    private func save() async {
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        do {
            try await environment.profileStore.update(.init(
                fitness_goal: goal,
                sex: sex,
                birth_year: birthYear,
                height_cm: heightCm,
                weight_kg: weightKg,
                activity_level: activityLevel
            ))
            step = .result
        } catch {
            errorMessage = error.userMessage
        }
    }

    /// "" löscht das Ziel serverseitig (der generierte Client kann kein explizites null senden).
    private func clearGoal() async {
        guard environment.profileStore.profile?.fitness_goal != nil else {
            dismiss()
            return
        }
        isSaving = true
        defer { isSaving = false }
        do {
            try await environment.profileStore.update(.init(fitness_goal: ""))
            dismiss()
        } catch {
            errorMessage = error.userMessage
        }
    }
}

/// Makro-Ziele + empfohlene Mahlzeiten — im Survey-Ergebnis und im Profil.
struct FitnessTargetsView: View {
    let profile: Components.Schemas.ProfileOut

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack(spacing: Spacing.sm) {
                if let protein = profile.target_protein_g {
                    Chip(title: "P \(protein) g", systemImage: "bolt.fill")
                }
                if let fat = profile.target_fat_g {
                    Chip(title: "F \(fat) g", systemImage: "drop.fill")
                }
                if let carbs = profile.target_carbs_g {
                    Chip(title: "K \(carbs) g", systemImage: "leaf.fill")
                }
            }
            if let meals = profile.recommended_meals_per_day {
                Text("weekplan.mealcount.recommended \(meals)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}
