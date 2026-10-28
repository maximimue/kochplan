import SwiftUI

/// Große, antippbare Auswahl-Kachel fürs Onboarding (Geräte, Supermärkte, Allergene, …).
struct TileToggle: View {
    let title: String
    var systemImage: String = "fork.knife"
    var isSelected: Bool
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: Spacing.xs) {
                Image(systemName: systemImage)
                    .font(.title2)
                Text(title)
                    .font(AppFont.metric)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
            }
            .frame(maxWidth: .infinity, minHeight: 72)
            .padding(Spacing.sm)
            .background(
                isSelected ? Color.accentColor.opacity(0.15) : AppColor.cardBackground,
                in: RoundedRectangle(cornerRadius: Radius.md)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Radius.md)
                    .strokeBorder(isSelected ? Color.accentColor : .clear, lineWidth: 2)
            )
            .foregroundStyle(isSelected ? Color.accentColor : .primary)
        }
        .buttonStyle(.plain)
    }
}

/// Raster aus `TileToggle`s für eine Vokabular-Kategorie — von Onboarding und Profil-Bearbeitung geteilt.
struct TileGrid: View {
    let keys: [String]
    let label: (String) -> String
    let icon: (String) -> String
    let isSelected: (String) -> Bool
    let toggle: (String) -> Void

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: Spacing.sm)], spacing: Spacing.sm) {
            ForEach(keys, id: \.self) { key in
                TileToggle(title: label(key), systemImage: icon(key), isSelected: isSelected(key)) {
                    toggle(key)
                }
            }
        }
    }
}

#Preview {
    HStack {
        TileToggle(title: "Backofen", systemImage: "flame.fill", isSelected: true) {}
        TileToggle(title: "Mikrowelle", systemImage: "waveform", isSelected: false) {}
    }
    .padding()
}
