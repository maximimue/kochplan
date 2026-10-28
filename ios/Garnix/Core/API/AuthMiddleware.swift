import Foundation
import HTTPTypes
import OpenAPIRuntime

/// Setzt den Access-Token-Header und versucht bei 401 genau einmal zu refreshen.
struct AuthMiddleware: ClientMiddleware {
    let authService: AuthService

    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        var firstRequest = request
        if let token = await authService.validAccessToken() {
            firstRequest.headerFields[.authorization] = "Bearer \(token)"
        }
        let (response, responseBody) = try await next(firstRequest, body, baseURL)

        guard response.status.code == 401, await authService.refreshIfNeeded() else {
            return (response, responseBody)
        }
        var retryRequest = request
        if let token = await authService.validAccessToken() {
            retryRequest.headerFields[.authorization] = "Bearer \(token)"
        }
        return try await next(retryRequest, body, baseURL)
    }
}

/// Mappt Server-Fehlerantworten (`{"error": {"code", "message"}}`) auf `AppError`. Muss in der
/// Middleware-Liste vor (= außerhalb von) `AuthMiddleware` stehen, damit die 401 erst den Refresh auslöst.
struct ErrorMappingMiddleware: ClientMiddleware {
    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        let (response, responseBody) = try await next(request, body, baseURL)
        guard !(200..<300).contains(response.status.code), let responseBody else {
            return (response, responseBody)
        }
        // Der Body ist eine Einweg-Sequenz: nach dem Einlesen durch eine frische `HTTPBody` ersetzen,
        // sonst scheitert das Decoding des generierten Clients mit "second iterator".
        let data = try await Data(collecting: responseBody, upTo: 1024 * 1024)
        if let decoded = try? JSONDecoder().decode(ServerErrorEnvelope.self, from: data) {
            throw AppError(code: decoded.error.code, message: decoded.error.message, rawResponseData: data)
        }
        return (response, HTTPBody(data))
    }
}

private struct ServerErrorEnvelope: Decodable {
    struct Body: Decodable {
        let code: String
        let message: String
    }
    let error: Body
}
