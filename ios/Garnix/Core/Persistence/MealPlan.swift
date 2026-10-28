import Foundation
import SwiftData

// ponytail: kein `isDirty` — diese Phase synct Pläne nur lesend (Pull + `generatePlan`),
// lokales Bearbeiten/Hochladen (PUT, 409/LWW, `ConflictResolver`) kommt mit der Plan-Bearbeitung.
@Model
final class MealPlan {
    @Attribute(.unique) var serverID: String
    /// Reiner Kalendertag (UTC-verankert), keine Uhrzeit — wie `week_start` vom Server.
    var weekStart: Date
    var totalCostCents: Int
    var budgetCents: Int?
    var overBudget: Bool
    var updatedAt: Date
    var clientUpdatedAt: Date
    var deletedAt: Date?
    @Relationship(deleteRule: .cascade, inverse: \PlanEntry.plan) var entries: [PlanEntry]

    init(
        serverID: String,
        weekStart: Date,
        totalCostCents: Int = 0,
        budgetCents: Int? = nil,
        overBudget: Bool = false,
        updatedAt: Date = .distantPast,
        clientUpdatedAt: Date = .distantPast,
        deletedAt: Date? = nil,
        entries: [PlanEntry] = []
    ) {
        self.serverID = serverID
        self.weekStart = weekStart
        self.totalCostCents = totalCostCents
        self.budgetCents = budgetCents
        self.overBudget = overBudget
        self.updatedAt = updatedAt
        self.clientUpdatedAt = clientUpdatedAt
        self.deletedAt = deletedAt
        self.entries = entries
    }
}

@Model
final class PlanEntry: Identifiable {
    var id: String { serverID }
    @Attribute(.unique) var serverID: String
    /// Reiner Kalendertag (UTC-verankert), keine Uhrzeit.
    var date: Date
    var meal: String
    var eatAtHour: Int?
    var eatAtMinute: Int?
    /// Alle Portionen des Haushalts (Einkauf, Kosten). Defaults an der Property für die SwiftData-Migration.
    var totalPortions: Double = 1
    /// Eigene Portion laut Fitnessziel (eigene Makros).
    var myPortion: Double = 1
    var recipeServerID: String?
    var recipeTitle: String?
    var totalMinutes: Int?
    var startAt: Date?
    var costCents: Int?
    var plan: MealPlan?

    init(
        serverID: String,
        date: Date,
        meal: String,
        eatAtHour: Int? = nil,
        eatAtMinute: Int? = nil,
        totalPortions: Double = 1,
        myPortion: Double = 1,
        recipeServerID: String? = nil,
        recipeTitle: String? = nil,
        totalMinutes: Int? = nil,
        startAt: Date? = nil,
        costCents: Int? = nil
    ) {
        self.serverID = serverID
        self.date = date
        self.meal = meal
        self.eatAtHour = eatAtHour
        self.eatAtMinute = eatAtMinute
        self.totalPortions = totalPortions
        self.myPortion = myPortion
        self.recipeServerID = recipeServerID
        self.recipeTitle = recipeTitle
        self.totalMinutes = totalMinutes
        self.startAt = startAt
        self.costCents = costCents
    }
}
