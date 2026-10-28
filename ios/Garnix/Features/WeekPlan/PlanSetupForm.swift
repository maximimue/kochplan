import SwiftUI

/// Welche Mahlzeiten bei welcher Anzahl pro Tag geplant werden (wichtigste zuerst, feste Uhrzeiten).
enum MealSlots {
    static let maxPerDay = priority.count

    private static let priority: [(meal: String, eatAt: String)] = [
        ("abend", "18:30:00"),
        ("mittag", "12:30:00"),
        ("fruehstueck", "08:00:00"),
        ("snack", "15:30:00"),
        ("snack", "10:30:00"),
    ]

    /// Chronologisch sortiert, z. B. 3 → Frühstück, Mittag, Abend.
    static func slots(count: Int) -> [(meal: String, eatAt: String)] {
        priority.prefix(max(1, min(count, maxPerDay))).sorted { $0.eatAt < $1.eatAt }
    }
}

/// Mahlzeiten pro Tag einstellen und Plan erstellen — im Leerzustand und beim Neu-Erstellen.
struct PlanSetupForm: View {
    @Environment(AppEnvironment.self) private var environment
    @Binding var mealCounts: [Int]
    let weekDates: [Date]
    let isGenerating: Bool
    let errorMessage: String?
    var showsIntro = false
    let onGenerate: () -> Void

    private var recommended: Int? { environment.profileStore.profile?.recommended_meals_per_day }

    /// Ausgewählt nur, wenn alle Tage gleich sind; Antippen setzt alle Tage.
    private var allDays: Binding<Int?> {
        Binding(
            get: { Set(mealCounts).count == 1 ? mealCounts.first : nil },
            set: { if let value = $0 { mealCounts = Array(repeating: value, count: mealCounts.count) } }
        )
    }

    var body: some View {
        Form {
            if showsIntro {
                Section {
                    Label {
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            Text("weekplan.empty.title").font(.headline)
                            Text("weekplan.empty.description").font(.subheadline).foregroundStyle(.secondary)
                        }
                    } icon: {
                        Image(systemName: "calendar.badge.plus").foregroundStyle(Color.accentColor)
                    }
                }
            }
            Section {
                Picker("weekplan.mealcount.all", selection: allDays) {
                    ForEach(1...MealSlots.maxPerDay, id: \.self) { count in
                        Text(verbatim: "\(count)").tag(Optional(count))
                    }
                }
                .pickerStyle(.segmented)
            } header: {
                Text("weekplan.mealcount.all")
            } footer: {
                if let recommended {
                    Text("weekplan.mealcount.recommended \(recommended)")
                }
            }
            Section("weekplan.mealcount.perDay") {
                ForEach(weekDates.indices, id: \.self) { index in
                    Stepper(value: $mealCounts[index], in: 1...MealSlots.maxPerDay) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(weekDates[index], format: .dateTime.weekday(.wide))
                            Text(verbatim: MealSlots.slots(count: mealCounts[index])
                                .map { environment.vocabCache.mealTypeLabel($0.meal) }
                                .joined(separator: " · "))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            Section {
                Button(action: onGenerate) {
                    Group {
                        if isGenerating { ProgressView() } else { Text("weekplan.generate.button").bold() }
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(isGenerating)
                .listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }
        }
    }
}
