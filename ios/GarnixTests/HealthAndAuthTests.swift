import Foundation
import HealthKit
import Testing
@testable import Garnix

@Suite
struct HealthAndAuthTests {
    @Test
    func mapsBiologicalSexToVocabKeys() {
        #expect(HealthService.sexKey(.female) == "weiblich")
        #expect(HealthService.sexKey(.male) == "maennlich")
        #expect(HealthService.sexKey(.other) == "divers")
        #expect(HealthService.sexKey(.notSet) == nil)
    }

    @Test
    func uploadsWeightOnlyOnNoticeableChange() {
        #expect(HealthService.shouldUpdateWeight(profileKg: 80, healthKg: 80.4) == false)
        #expect(HealthService.shouldUpdateWeight(profileKg: 80, healthKg: 79.5) == true)
        #expect(HealthService.shouldUpdateWeight(profileKg: nil, healthKg: 70) == true)
        #expect(HealthService.shouldUpdateWeight(profileKg: 80, healthKg: nil) == false)
    }

    @Test
    func nonceHashMatchesServerSideSha256() {
        // Server: hashlib.sha256(raw_nonce.encode()).hexdigest()
        #expect(AppleNonce.sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        let nonce = AppleNonce.random()
        #expect(nonce.count == 64 && nonce != AppleNonce.random())
    }
}
