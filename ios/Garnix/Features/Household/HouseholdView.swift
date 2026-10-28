import SwiftUI

/// Gemeinsamer Haushalt: Mitglieder, Einladungscode teilen, beitreten, verlassen.
/// Geteilt werden Wochenpläne, Einkaufsliste, Supermarkt, Budget und Geräte; Allergien,
/// Ernährungsform, Fitness und Health-Daten bleiben persönlich.
struct HouseholdView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var household: Components.Schemas.HouseholdOut?
    @State private var isWorking = false
    @State private var isConfirmingLeave = false
    @State private var errorMessage: String?

    var body: some View {
        List {
            if let household {
                Section("household.section.members") {
                    ForEach(household.members, id: \.id) { member in
                        HStack {
                            Text(verbatim: member.display_name ?? member.email ?? String(localized: "household.member.unnamed"))
                            if member.is_me {
                                Text("household.member.me").font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if member.has_fitness_goal {
                                Image(systemName: "figure.run")
                                    .foregroundStyle(Color.accentColor)
                                    .accessibilityLabel(Text("household.member.fitness"))
                            }
                        }
                    }
                    LabeledContent("household.size", value: "\(household.household_size)")
                }
                inviteSection(household)
                Section {
                    JoinHouseholdForm(requiresConfirmation: true) { await load() }
                } header: {
                    Text("household.section.join")
                } footer: {
                    Text("household.join.footer")
                }
                if household.members.count > 1 {
                    Section {
                        Button("household.leave.button", role: .destructive) { isConfirmingLeave = true }
                            .disabled(isWorking)
                    } footer: {
                        Text("household.leave.footer")
                    }
                }
            } else if errorMessage == nil {
                ProgressView()
            }
            if let errorMessage {
                Text(errorMessage).foregroundStyle(.red)
            }
        }
        .navigationTitle("household.title")
        .task { await load() }
        .refreshable { await load() }
        .confirmationDialog("household.leave.confirm", isPresented: $isConfirmingLeave, titleVisibility: .visible) {
            Button("household.leave.button", role: .destructive) { Task { await leave() } }
        }
    }

    @ViewBuilder
    private func inviteSection(_ household: Components.Schemas.HouseholdOut) -> some View {
        Section {
            if let code = household.invite_code {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text(verbatim: code)
                        .font(.system(.title, design: .monospaced).weight(.bold))
                        .textSelection(.enabled)
                    if let expiresAt = household.invite_expires_at {
                        Text("household.invite.expires \(expiresAt.formatted(date: .abbreviated, time: .shortened))")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                ShareLink(item: String(localized: "household.invite.shareText \(code)")) {
                    Label("household.invite.share", systemImage: "square.and.arrow.up")
                }
            }
            Button(household.invite_code == nil ? "household.invite.create" : "household.invite.renew") {
                Task { await createInvite() }
            }
            .disabled(isWorking)
        } header: {
            Text("household.section.invite")
        } footer: {
            Text("household.invite.footer")
        }
    }

    private func load() async {
        do {
            let response = try await environment.apiClient.client.getHousehold(.init())
            household = try response.ok.body.json
            errorMessage = nil
        } catch {
            errorMessage = error.userMessage
        }
    }

    private func createInvite() async {
        isWorking = true
        defer { isWorking = false }
        do {
            household = try await environment.apiClient.client.createHouseholdInvite(.init()).ok.body.json
        } catch {
            errorMessage = error.userMessage
        }
    }

    private func leave() async {
        isWorking = true
        defer { isWorking = false }
        do {
            household = try await environment.apiClient.client.leaveHousehold(.init()).ok.body.json
            try await environment.refreshAfterHouseholdChange()
        } catch {
            errorMessage = error.userMessage
        }
    }
}

/// Code eingeben und beitreten — im Haushalts-Screen und im Onboarding (neues Familienmitglied).
struct JoinHouseholdForm: View {
    @Environment(AppEnvironment.self) private var environment
    /// Im Profil warnen, dass die eigenen Pläne ersetzt werden; im Onboarding gibt es noch keine.
    let requiresConfirmation: Bool
    var onJoined: () async -> Void = {}

    @State private var code = ""
    @State private var isJoining = false
    @State private var isConfirming = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            TextField("household.join.placeholder", text: $code)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .font(.system(.body, design: .monospaced))
            Button {
                if requiresConfirmation { isConfirming = true } else { Task { await join() } }
            } label: {
                if isJoining { ProgressView() } else { Text("household.join.button") }
            }
            .disabled(code.trimmingCharacters(in: .whitespaces).count < 4 || isJoining)
            if let errorMessage {
                Text(errorMessage).font(.footnote).foregroundStyle(.red)
            }
        }
        .confirmationDialog("household.join.confirm", isPresented: $isConfirming, titleVisibility: .visible) {
            Button("household.join.button") { Task { await join() } }
        }
    }

    private func join() async {
        isJoining = true
        errorMessage = nil
        defer { isJoining = false }
        do {
            _ = try await environment.apiClient.client.joinHousehold(.init(body: .json(.init(code: code)))).ok.body.json
            try await environment.refreshAfterHouseholdChange()
            code = ""
            await onJoined()
        } catch {
            errorMessage = error.userMessage
        }
    }
}
