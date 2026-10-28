import AuthenticationServices
import SwiftUI

/// Erster Bildschirm, solange niemand angemeldet ist — macht den Login-Schritt sichtbar
/// statt ihn im Profil-Tab zu verstecken.
struct LoginGateView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(\.colorScheme) private var colorScheme
    @State private var currentNonce: String?
    @State private var isSigningIn = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: Spacing.lg) {
                Spacer()
                Image(systemName: "fork.knife.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(Color.accentColor)
                Text("login.title")
                    .font(.largeTitle.bold())
                Text("login.subtitle")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Spacer()
                SignInWithAppleButton(.signIn) { request in
                    let nonce = AppleNonce.random()
                    currentNonce = nonce
                    request.requestedScopes = [.fullName, .email]
                    request.nonce = AppleNonce.sha256(nonce)
                } onCompletion: { result in
                    Task { await handle(result) }
                }
                .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                .frame(height: 50)
                .disabled(isSigningIn)
                if isSigningIn {
                    ProgressView()
                }
                if let errorMessage {
                    Text(errorMessage).font(.footnote).foregroundStyle(.red)
                }
                #if DEBUG
                DevLoginView(authService: environment.authService)
                #endif
            }
            .padding(Spacing.lg)
            .multilineTextAlignment(.center)
        }
    }

    private func handle(_ result: Result<ASAuthorization, any Error>) async {
        errorMessage = nil
        switch result {
        case .failure(let error):
            if (error as? ASAuthorizationError)?.code != .canceled {
                errorMessage = error.userMessage
            }
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let idToken = String(data: tokenData, encoding: .utf8),
                  let nonce = currentNonce
            else {
                errorMessage = String(localized: "login.apple.failed")
                return
            }
            // Den Namen liefert Apple nur beim allerersten Login — der Server speichert ihn dann.
            let name = credential.fullName
                .map { PersonNameComponentsFormatter.localizedString(from: $0, style: .default) }
                .flatMap { $0.isEmpty ? nil : $0 }
            isSigningIn = true
            defer { isSigningIn = false }
            do {
                try await environment.authService.loginApple(
                    idToken: idToken, rawNonce: nonce, displayName: name, appleUserID: credential.user
                )
            } catch {
                errorMessage = error.userMessage
            }
        }
    }
}

#if DEBUG
struct DevLoginView: View {
    let authService: AuthService
    @State private var email = ""
    @State private var error: String?

    var body: some View {
        Form {
            Section("profile.devlogin.title") {
                TextField("profile.devlogin.email.placeholder", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                Button("profile.devlogin.button") {
                    Task { await login() }
                }
                .disabled(email.isEmpty)
                if let error {
                    Text(error).foregroundStyle(.red)
                }
            }
        }
        .frame(minHeight: 180)
        .scrollDisabled(true)
    }

    private func login() async {
        error = nil
        do {
            try await authService.devLogin(email: email)
        } catch {
            self.error = error.userMessage
        }
    }
}
#endif
