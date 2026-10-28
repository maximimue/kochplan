import SwiftUI
import SwiftData

@main
struct GarnixApp: App {
    let modelContainer: ModelContainer
    @State private var environment: AppEnvironment

    init() {
        let container: ModelContainer
        do {
            container = try ModelContainer(for: Recipe.self, MealPlan.self)
        } catch {
            fatalError("ModelContainer konnte nicht erstellt werden: \(error)")
        }
        modelContainer = container
        _environment = State(initialValue: AppEnvironment(modelContainer: container))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
        }
        .modelContainer(modelContainer)
    }
}
