import Foundation
import Testing
@testable import Garnix

@Suite
struct StartTimeCalculatorTests {
    private let berlin = TimeZone(identifier: "Europe/Berlin")!

    @Test
    func simple() {
        // 18:30 Essen, 45 min Rezept, 10 min Puffer -> 17:35 Ortszeit (CEST = UTC+2) = 15:35 UTC.
        let result = StartTimeCalculator.computeStartAt(
            date: DateComponents(year: 2026, month: 6, day: 10),
            eatAt: DateComponents(hour: 18, minute: 30),
            totalMinutes: 45, timeZone: berlin, bufferMinutes: 10
        )
        #expect(result == utc(2026, 6, 10, 15, 35))
    }

    @Test
    func acrossDSTChange() {
        // 25.10.2026: Uhren 03:00 CEST -> 02:00 CET. Essen 03:30 CET = 02:30 UTC.
        // 120 min vorher = 00:30 UTC. Wanduhr-Rechnung ergäbe fälschlich 01:30.
        let result = StartTimeCalculator.computeStartAt(
            date: DateComponents(year: 2026, month: 10, day: 25),
            eatAt: DateComponents(hour: 3, minute: 30),
            totalMinutes: 120, timeZone: berlin, bufferMinutes: 0
        )
        #expect(result == utc(2026, 10, 25, 0, 30))
    }

    @Test
    func noEatTime() {
        let result = StartTimeCalculator.computeStartAt(
            date: DateComponents(year: 2026, month: 1, day: 1),
            eatAt: nil, totalMinutes: 30, timeZone: berlin, bufferMinutes: 10
        )
        #expect(result == nil)
    }

    private func utc(_ year: Int, _ month: Int, _ day: Int, _ hour: Int, _ minute: Int) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar.date(from: DateComponents(year: year, month: month, day: day, hour: hour, minute: minute))!
    }
}
