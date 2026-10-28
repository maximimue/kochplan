import Foundation

enum StartTimeCalculator {
    /// Startzeit = Essenszeit − Gesamtdauer − Puffer, absolut gerechnet (DST-sicher): die
    /// Wanduhr-Essenszeit wird einmal in einen absoluten Zeitpunkt aufgelöst, danach wird nur
    /// noch mit Sekunden gerechnet, nie wieder über Kalenderfelder — sonst ist das Ergebnis an
    /// Zeitumstellungstagen falsch.
    static func computeStartAt(
        date: DateComponents, eatAt: DateComponents?, totalMinutes: Int,
        timeZone: TimeZone, bufferMinutes: Int
    ) -> Date? {
        guard let eatAt, let hour = eatAt.hour, let minute = eatAt.minute else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        var components = date
        components.hour = hour
        components.minute = minute
        components.second = 0
        components.timeZone = timeZone
        guard let eatDate = calendar.date(from: components) else { return nil }
        return eatDate.addingTimeInterval(-Double((totalMinutes + bufferMinutes) * 60))
    }
}
