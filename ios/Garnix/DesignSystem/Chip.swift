import SwiftUI

/// Kleines Label in Pillenform — für Filter, Kennzahlen und Allergen-Hinweise.
///
/// `title` wird bewusst immer **verbatim** angezeigt (Vokabular-Keys, bereits formatierte
/// Werte wie "25 min") — für echte UI-Labels aus `Localizable.xcstrings` `init(titleKey:)`
/// verwenden, sonst würde der rohe Key angezeigt statt übersetzt zu werden.
struct Chip: View {
    let text: Text
    var systemImage: String?
    var isSelected: Bool = false

    init(title: String, systemImage: String? = nil, isSelected: Bool = false) {
        self.text = Text(verbatim: title)
        self.systemImage = systemImage
        self.isSelected = isSelected
    }

    init(titleKey: LocalizedStringKey, systemImage: String? = nil, isSelected: Bool = false) {
        self.text = Text(titleKey)
        self.systemImage = systemImage
        self.isSelected = isSelected
    }

    var body: some View {
        HStack(spacing: 4) {
            if let systemImage {
                Image(systemName: systemImage)
            }
            text
        }
        .font(AppFont.metric)
        .padding(.horizontal, Spacing.sm)
        .padding(.vertical, Spacing.xs)
        .background(isSelected ? Color.accentColor.opacity(0.2) : AppColor.cardBackground, in: .capsule)
        .foregroundStyle(isSelected ? Color.accentColor : .primary)
    }
}

#Preview {
    HStack {
        Chip(title: "25 min", systemImage: "clock")
        Chip(title: "Abend", isSelected: true)
        Chip(title: "Gluten", systemImage: "exclamationmark.triangle")
    }
    .padding()
}
