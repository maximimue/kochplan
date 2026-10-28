import Foundation

enum PlanMapper {
    static func apply(_ dto: Components.Schemas.PlanOut, to plan: MealPlan) throws {
        plan.weekStart = try parseDate(dto.week_start)
        plan.totalCostCents = dto.total_cost_cents
        plan.budgetCents = dto.budget_cents
        plan.overBudget = dto.over_budget
        plan.updatedAt = dto.updated_at
        plan.clientUpdatedAt = dto.client_updated_at
        plan.deletedAt = (dto.deleted == true) ? dto.updated_at : nil

        let existingByID = Dictionary(uniqueKeysWithValues: plan.entries.map { ($0.serverID, $0) })
        plan.entries = try dto.entries.map { entryDTO in
            let entry = existingByID[entryDTO.id] ?? PlanEntry(serverID: entryDTO.id, date: .distantPast, meal: entryDTO.meal)
            try apply(entryDTO, to: entry)
            return entry
        }
    }

    static func apply(_ dto: Components.Schemas.PlanEntryOut, to entry: PlanEntry) throws {
        entry.date = try parseDate(dto.date)
        entry.meal = dto.meal
        if let eatAt = dto.eat_at, let components = parseTime(eatAt) {
            entry.eatAtHour = components.hour
            entry.eatAtMinute = components.minute
        } else {
            entry.eatAtHour = nil
            entry.eatAtMinute = nil
        }
        entry.totalPortions = dto.total_portions
        entry.myPortion = dto.my_portion
        entry.recipeServerID = dto.recipe_id
        entry.recipeTitle = dto.recipe_title
        entry.totalMinutes = dto.total_minutes
        entry.startAt = dto.start_at
        entry.costCents = dto.cost_cents
    }

    /// `week_start`/`date` kommen vom Server als reines ISO-Datum ("2026-06-10"), nicht als
    /// `date-time` — der Generator erzeugt dafür `String`, nicht `Date`.
    static func parseDate(_ string: String) throws -> Date {
        guard let date = dateFormatter.date(from: string) else {
            throw AppError(code: "invalid_date", message: "Ungültiges Datum: \(string)")
        }
        return date
    }

    static func format(date: Date) -> String {
        dateFormatter.string(from: date)
    }

    private static func format(hour: Int, minute: Int) -> String {
        String(format: "%02d:%02d:00", hour, minute)
    }

    /// Baut die PUT-Repräsentation eines lokalen Eintrags, optional mit getauschter Rezept-ID.
    static func planEntryIn(from entry: PlanEntry, overridingRecipeID newRecipeID: String? = nil) -> Components.Schemas.PlanEntryIn {
        let eatAt: String?
        if let hour = entry.eatAtHour, let minute = entry.eatAtMinute {
            eatAt = format(hour: hour, minute: minute)
        } else {
            eatAt = nil
        }
        return .init(
            id: entry.serverID,
            date: format(date: entry.date),
            meal: entry.meal,
            eat_at: eatAt,
            recipe_id: newRecipeID ?? entry.recipeServerID
        )
    }

    private static func parseTime(_ string: String) -> DateComponents? {
        guard let date = timeFormatter.date(from: string) else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar.dateComponents([.hour, .minute], from: date)
    }

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let timeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "HH:mm:ss"
        return f
    }()
}
