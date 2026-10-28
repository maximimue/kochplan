import Foundation
import HealthKit

/// Liest Körperdaten aus Apple Health — nur lesend und nur fürs eigene Profil (Bedarfsrechnung);
/// Health-Daten anderer Haushaltsmitglieder sieht niemand.
final class HealthService: Sendable {
    struct BodyData: Equatable, Sendable {
        var weightKg: Double?
        var heightCm: Int?
        var birthYear: Int?
        var sex: String?
    }

    private let store = HKHealthStore()
    private static let weightSyncKey = "health.weightSync"

    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Gewicht beim App-Start automatisch übernehmen — aktiv, sobald einmal „Aus Health übernehmen“ genutzt wurde.
    var isWeightSyncEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: Self.weightSyncKey) }
        set { UserDefaults.standard.set(newValue, forKey: Self.weightSyncKey) }
    }

    func requestAuthorization() async throws {
        let read: Set<HKObjectType> = [
            HKQuantityType(.bodyMass), HKQuantityType(.height),
            HKCharacteristicType(.dateOfBirth), HKCharacteristicType(.biologicalSex),
        ]
        try await store.requestAuthorization(toShare: [], read: read)
    }

    /// Fehlende Freigaben liefern einfach `nil` — HealthKit verrät aus Datenschutzgründen nicht, ob gelesen werden darf.
    func readBodyData() async -> BodyData {
        let weight = await latest(.bodyMass, unit: .gramUnit(with: .kilo))
        let height = await latest(.height, unit: .meterUnit(with: .centi))
        return BodyData(
            weightKg: weight.map { ($0 * 10).rounded() / 10 },
            heightCm: height.map { Int($0.rounded()) },
            birthYear: (try? store.dateOfBirthComponents())?.year,
            sex: (try? store.biologicalSex()).flatMap { Self.sexKey($0.biologicalSex) }
        )
    }

    private func latest(_ identifier: HKQuantityTypeIdentifier, unit: HKUnit) async -> Double? {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: HKQuantityType(identifier))],
            sortDescriptors: [SortDescriptor(\.endDate, order: .reverse)],
            limit: 1
        )
        return try? await descriptor.result(for: store).first?.quantity.doubleValue(for: unit)
    }

    /// Vokabular-Key aus `/v1/meta/vocab` (`sexes`); „nicht festgelegt“ bleibt leer.
    static func sexKey(_ sex: HKBiologicalSex) -> String? {
        switch sex {
        case .female: "weiblich"
        case .male: "maennlich"
        case .other: "divers"
        default: nil
        }
    }

    /// Kleine Schwankungen nicht hochladen — der Tagesbedarf ändert sich erst bei spürbarer Differenz.
    static func shouldUpdateWeight(profileKg: Double?, healthKg: Double?) -> Bool {
        guard let healthKg else { return false }
        guard let profileKg else { return true }
        return abs(healthKg - profileKg) >= 0.5
    }
}
