import Foundation

@MainActor
@Observable
final class ProfileStore {
    private(set) var profile: Components.Schemas.ProfileOut?
    private let api: any APIProtocol

    init(api: any APIProtocol) {
        self.api = api
    }

    func refresh() async throws {
        let response = try await api.getMe(.init())
        guard case let .ok(ok) = response, case let .json(profile) = ok.body else {
            throw AppError(code: "profile_failed", message: "Profil konnte nicht geladen werden.")
        }
        self.profile = profile
    }

    func update(_ patch: Components.Schemas.ProfilePatch) async throws {
        let response = try await api.updateMe(.init(body: .json(patch)))
        guard case let .ok(ok) = response, case let .json(profile) = ok.body else {
            throw AppError(code: "profile_failed", message: "Profil konnte nicht gespeichert werden.")
        }
        self.profile = profile
    }

    func reset() {
        profile = nil
    }

    func delete() async throws {
        let response = try await api.deleteMe(.init())
        guard case .noContent = response else {
            throw AppError(code: "profile_failed", message: "Konto konnte nicht gelöscht werden.")
        }
        profile = nil
    }
}
