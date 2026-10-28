import Foundation
import UserNotifications

/// Lokale Erinnerung zur Kochstartzeit. Re-Scheduling ist idempotent: vor dem Neuplanen werden
/// **alle** Kochstart-Erinnerungen entfernt, auch die ersetzter oder gelöschter Einträge.
/// Nimmt bewusst keine SwiftData-Models entgegen (`ModelContext` nie über Actor-/Task-Grenzen).
enum NotificationScheduler {
    struct Entry: Sendable {
        let id: String
        let startAt: Date
        let recipeTitle: String?
    }

    static func requestAuthorization() async {
        _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])
    }

    static func reschedule(for entries: [Entry]) async {
        let center = UNUserNotificationCenter.current()
        let stale = await center.pendingNotificationRequests().map(\.identifier).filter { $0.hasPrefix(prefix) }
        center.removePendingNotificationRequests(withIdentifiers: stale)

        for entry in entries where entry.startAt > Date() {
            let content = UNMutableNotificationContent()
            content.title = String(localized: "notification.start.title")
            content.body = entry.recipeTitle ?? String(localized: "notification.start.body")
            content.sound = .default

            let trigger = UNCalendarNotificationTrigger(
                dateMatching: Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: entry.startAt),
                repeats: false
            )
            let request = UNNotificationRequest(identifier: identifier(for: entry.id), content: content, trigger: trigger)
            try? await center.add(request)
        }
    }

    private static let prefix = "start-"
    private static func identifier(for entryID: String) -> String { prefix + entryID }
}
