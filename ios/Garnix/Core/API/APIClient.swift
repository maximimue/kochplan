import Foundation
import OpenAPIRuntime
import OpenAPIURLSession

/// Authentifizierter Client für alle Endpunkte außer `/auth/*` (dafür `AuthService`).
struct APIClient {
    let client: any APIProtocol

    init(baseURL: URL, authService: AuthService) {
        self.client = Client(
            serverURL: baseURL,
            configuration: .garnix,
            transport: URLSessionTransport(),
            middlewares: [ErrorMappingMiddleware(), AuthMiddleware(authService: authService)]
        )
    }
}

extension Configuration {
    /// Der Server formatiert Zeitstempel uneinheitlich: `updated_at` (aus `datetime.now()`) hat
    /// Sekundenbruchteile (`"...T16:31:32.110682Z"`), ein berechnetes `start_at`
    /// (`compute_start_at`, glatte Sekunde) dagegen nicht (`"...T17:10:00Z"`). Ein starr auf
    /// ein Format eingestellter `ISO8601DateTranscoder` scheitert an jeweils der anderen
    /// Variante — deshalb `FlexibleISO8601DateTranscoder`, der beide probiert.
    static let garnix = Configuration(dateTranscoder: FlexibleISO8601DateTranscoder())
}

struct FlexibleISO8601DateTranscoder: DateTranscoder {
    private let withFractionalSeconds = ISO8601DateTranscoder(options: [.withInternetDateTime, .withFractionalSeconds])
    private let withoutFractionalSeconds = ISO8601DateTranscoder(options: [.withInternetDateTime])

    func encode(_ date: Date) throws -> String {
        try withFractionalSeconds.encode(date)
    }

    func decode(_ string: String) throws -> Date {
        if let date = try? withFractionalSeconds.decode(string) {
            return date
        }
        return try withoutFractionalSeconds.decode(string)
    }
}

extension JSONDecoder {
    /// Für manuelles Dekodieren von Server-JSON außerhalb des generierten Client-Pfads
    /// (z. B. den `server_version`-Payload bei 409-Sync-Konflikten) — gleiche Datumsbehandlung
    /// wie `.garnix`-Configuration.
    static let garnix: JSONDecoder = {
        let decoder = JSONDecoder()
        let transcoder = FlexibleISO8601DateTranscoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)
            return try transcoder.decode(string)
        }
        return decoder
    }()
}
