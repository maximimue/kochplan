import Foundation
import HTTPTypes
import OpenAPIRuntime

/// Liefert vordefinierte JSON-Antworten statt echter Netzwerk-Calls, ein Eintrag je Aufruf
/// (letzter Eintrag wird bei weiteren Aufrufen wiederholt). Zeichnet die angefragten Pfade auf.
actor MockClientTransport: ClientTransport {
    private let responses: [Data]
    private(set) var requestPaths: [String] = []
    private var callIndex = 0

    init(responses: [Data]) {
        self.responses = responses
    }

    func send(
        _ request: HTTPRequest, body: HTTPBody?, baseURL: URL, operationID: String
    ) async throws -> (HTTPResponse, HTTPBody?) {
        requestPaths.append(request.path ?? "")
        let data = responses[min(callIndex, responses.count - 1)]
        callIndex += 1
        return (HTTPResponse(status: .ok), HTTPBody(data))
    }
}
