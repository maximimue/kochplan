import Foundation
import Testing
@testable import Garnix

@Suite
struct FlexibleISO8601DateTranscoderTests {
    private let transcoder = FlexibleISO8601DateTranscoder()

    @Test
    func decodesWithFractionalSeconds() throws {
        // z. B. `updated_at` aus `datetime.now()`.
        let date = try transcoder.decode("2026-10-27T16:31:32.110682Z")
        #expect(date.timeIntervalSince1970.rounded() == 1_793_118_692)
    }

    @Test
    func decodesWithoutFractionalSeconds() throws {
        // z. B. `start_at` aus `compute_start_at` (glatte Sekunde).
        let date = try transcoder.decode("2026-10-26T17:10:00Z")
        #expect(date.timeIntervalSince1970.rounded() == 1_793_034_600)
    }

    @Test
    func throwsOnGarbage() {
        #expect(throws: (any Error).self) {
            try transcoder.decode("nicht-ein-datum")
        }
    }
}
