import SwiftUI
import UIKit

/// Vollbild, ein Schritt pro Seite (Swipe oder Buttons), Bildschirm bleibt an.
struct CookingModeView: View {
    let recipe: Recipe
    @Environment(\.dismiss) private var dismiss
    @State private var stepIndex = 0

    private var steps: [Recipe.Step] { recipe.decodedSteps }

    var body: some View {
        NavigationStack {
            TabView(selection: $stepIndex) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    StepPageView(
                        step: step, index: index, total: steps.count,
                        onPrevious: { withAnimation { stepIndex = max(0, stepIndex - 1) } },
                        onNext: { withAnimation { stepIndex = min(steps.count - 1, stepIndex + 1) } }
                    )
                    .tag(index)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            .navigationTitle(recipe.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("cooking.close") { dismiss() }
                }
            }
        }
        .onAppear { UIApplication.shared.isIdleTimerDisabled = true }
        .onDisappear { UIApplication.shared.isIdleTimerDisabled = false }
    }
}

private struct StepPageView: View {
    let step: Recipe.Step
    let index: Int
    let total: Int
    let onPrevious: () -> Void
    let onNext: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.xl) {
                (Text("cooking.step.label") + Text(verbatim: " ") + Text(index + 1, format: .number)
                    + Text(verbatim: "/") + Text(total, format: .number))
                    .font(AppFont.sectionTitle)
                    .foregroundStyle(.secondary)

                Text(step.text)
                    .font(.title2)
                    .multilineTextAlignment(.center)

                if let minutes = step.minutes {
                    StepTimerView(minutes: minutes)
                }
            }
            .padding(Spacing.lg)
            .frame(maxWidth: .infinity)
        }
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: Spacing.md) {
                Button {
                    onPrevious()
                } label: {
                    Label("cooking.previous", systemImage: "chevron.left")
                }
                .disabled(index == 0)

                Spacer()

                Button {
                    onNext()
                } label: {
                    Label("cooking.next", systemImage: "chevron.right")
                }
                .disabled(index == total - 1)
            }
            .buttonStyle(.bordered)
            .font(.title3)
            .padding(Spacing.md)
            .background(.regularMaterial)
        }
    }
}

private struct StepTimerView: View {
    let minutes: Int
    @State private var endDate: Date?

    var body: some View {
        if let endDate {
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let remaining = max(0, endDate.timeIntervalSince(context.date))
                VStack(spacing: Spacing.sm) {
                    Text(verbatim: remainingLabel(remaining))
                        .font(.system(.largeTitle, design: .monospaced))
                        .monospacedDigit()
                    Button("cooking.timer.cancel") { self.endDate = nil }
                }
                .sensoryFeedback(.success, trigger: remaining == 0)
            }
        } else {
            Button {
                endDate = Date().addingTimeInterval(Double(minutes * 60))
            } label: {
                Label("cooking.timer.start", systemImage: "timer")
            }
            .buttonStyle(.bordered)
        }
    }

    private func remainingLabel(_ seconds: TimeInterval) -> String {
        let total = Int(seconds.rounded())
        return String(format: "%02d:%02d", total / 60, total % 60)
    }
}
