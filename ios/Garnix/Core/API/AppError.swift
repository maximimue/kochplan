import Foundation
import OpenAPIRuntime

/// Lokalisierte Server-Fehlermeldung (`{"error": {"code", "message"}}`). Transportfehler
/// (offline, Timeout) bekommen eigene, lokale Texte statt einer Server-Message.
struct AppError: Error, LocalizedError {
    let code: String
    let message: String
    /// Rohe Antwort, falls eine Fehlerantwort zusätzliche Felder über `{error:...}` hinaus
    /// trägt (z. B. `server_version` bei 409 Sync-Konflikten).
    var rawResponseData: Data?

    init(code: String, message: String, rawResponseData: Data? = nil) {
        self.code = code
        self.message = message
        self.rawResponseData = rawResponseData
    }

    var errorDescription: String? { message }
}

extension AppError {
    static let offline = AppError(code: "offline", message: String(localized: "error.offline"))
    static let timeout = AppError(code: "timeout", message: String(localized: "error.timeout"))
}

extension Error {
    /// Der OpenAPI-Runtime verpackt Fehler aus Middlewares und Transport in `ClientError` —
    /// hier wieder auspacken; Transportfehler werden auf lokale Offline-/Timeout-Texte abgebildet.
    var appError: AppError? {
        switch self {
        case let error as AppError: error
        case let error as ClientError: error.underlyingError.appError
        case let error as URLError where error.code == .timedOut: .timeout
        case is URLError: .offline
        default: nil
        }
    }

    /// Für die Anzeige: Server-Meldung bzw. Offline-/Timeout-Text statt der technischen `ClientError`-Beschreibung.
    var userMessage: String { appError?.message ?? localizedDescription }
}
