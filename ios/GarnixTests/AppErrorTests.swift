import Foundation
import Testing
import OpenAPIRuntime
@testable import Garnix

@Suite
struct AppErrorTests {
    private func wrapped(_ error: any Error) -> any Error {
        ClientError(operationID: "upsertPlan", operationInput: "", causeDescription: "Middleware threw", underlyingError: error)
    }

    @Test
    func unwrapsServerErrorFromClientError() {
        let error = wrapped(AppError(code: "sync_conflict", message: "Neuere Version auf dem Server."))
        #expect(error.appError?.code == "sync_conflict")
        #expect(error.userMessage == "Neuere Version auf dem Server.")
    }

    @Test
    func mapsTransportErrorsToLocalTexts() {
        #expect(wrapped(URLError(.timedOut)).appError?.code == "timeout")
        #expect(wrapped(URLError(.cannotFindHost)).appError?.code == "offline")
        #expect(CocoaError(.fileNoSuchFile).appError == nil)
    }
}
