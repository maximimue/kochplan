import AuthenticationServices
import CryptoKit
import Foundation
import OpenAPIRuntime
import OpenAPIURLSession

@MainActor
@Observable
final class AuthService {
    private(set) var isAuthenticated: Bool
    private let baseURL: URL
    private let rawClient: any APIProtocol
    private var refreshTask: Task<Bool, Never>?

    init(baseURL: URL) {
        self.baseURL = baseURL
        self.rawClient = Client(
            serverURL: baseURL, configuration: .garnix, transport: URLSessionTransport(),
            middlewares: [ErrorMappingMiddleware()]
        )
        self.isAuthenticated = KeychainStore.read(forKey: Keys.accessToken) != nil
    }

    func validAccessToken() -> String? {
        KeychainStore.read(forKey: Keys.accessToken)
    }

    func logout() {
        KeychainStore.delete(forKey: Keys.accessToken)
        KeychainStore.delete(forKey: Keys.refreshToken)
        KeychainStore.delete(forKey: Keys.appleUserID)
        isAuthenticated = false
    }

    /// Server prüft Signatur, Audience (Bundle-ID) und dass das Token `sha256(rawNonce)` enthält.
    func loginApple(idToken: String, rawNonce: String, displayName: String?, appleUserID: String) async throws {
        let output = try await rawClient.loginApple(.init(body: .json(.init(
            id_token: idToken, raw_nonce: rawNonce, display_name: displayName
        ))))
        let token = try output.ok.body.json
        KeychainStore.save(appleUserID, forKey: Keys.appleUserID)
        store(accessToken: token.access_token, refreshToken: token.refresh_token)
    }

    /// Apple verlangt, auf zurückgezogene Anmeldungen zu reagieren (Einstellungen → Apple-ID → Mit Apple anmelden).
    func checkAppleCredentialState() async {
        guard let appleUserID = KeychainStore.read(forKey: Keys.appleUserID) else { return }
        let state = try? await ASAuthorizationAppleIDProvider().credentialState(forUserID: appleUserID)
        if state == .revoked || state == .notFound {
            logout()
        }
    }

    /// Bei 401 genau ein Refresh-Versuch, parallele Aufrufe warten auf denselben Task.
    func refreshIfNeeded() async -> Bool {
        if let refreshTask { return await refreshTask.value }
        let task = Task { await performRefresh() }
        refreshTask = task
        let result = await task.value
        refreshTask = nil
        return result
    }

    #if DEBUG
    /// Nur Debug-Builds: `/v1/auth/dev` ist bewusst `include_in_schema=False` und daher
    /// nicht im generierten OpenAPI-Client enthalten.
    func devLogin(email: String) async throws {
        var request = URLRequest(url: baseURL.appendingPathComponent("v1/auth/dev"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["email": email])

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw AppError.offline
        }
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw AppError(code: "dev_login_failed", message: String(localized: "error.dev_login_failed"))
        }
        let token = try JSONDecoder().decode(DevLoginResponse.self, from: data)
        store(accessToken: token.accessToken, refreshToken: token.refreshToken)
    }
    #endif

    private func performRefresh() async -> Bool {
        guard let refreshToken = KeychainStore.read(forKey: Keys.refreshToken) else {
            logout()
            return false
        }
        guard let output = try? await rawClient.refreshToken(.init(body: .json(.init(refresh_token: refreshToken)))),
              case let .ok(ok) = output,
              case let .json(token) = ok.body
        else {
            logout()
            return false
        }
        store(accessToken: token.access_token, refreshToken: token.refresh_token)
        return true
    }

    private func store(accessToken: String, refreshToken: String) {
        KeychainStore.save(accessToken, forKey: Keys.accessToken)
        KeychainStore.save(refreshToken, forKey: Keys.refreshToken)
        isAuthenticated = true
    }

    private enum Keys {
        static let accessToken = "accessToken"
        static let refreshToken = "refreshToken"
        static let appleUserID = "appleUserID"
    }
}

/// Nonce für Sign in with Apple: Apple bettet `sha256(raw)` ins ID-Token ein, der Server vergleicht mit `raw`
/// — so kann ein abgefangenes Token nicht wiederverwendet werden.
enum AppleNonce {
    static func random(byteCount: Int = 32) -> String {
        var bytes = [UInt8](repeating: 0, count: byteCount)
        precondition(SecRandomCopyBytes(kSecRandomDefault, byteCount, &bytes) == errSecSuccess, "Keine Zufallsbytes verfügbar")
        return bytes.map { String(format: "%02x", $0) }.joined()
    }

    static func sha256(_ input: String) -> String {
        SHA256.hash(data: Data(input.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}

#if DEBUG
private struct DevLoginResponse: Decodable {
    let accessToken: String
    let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
    }
}
#endif
