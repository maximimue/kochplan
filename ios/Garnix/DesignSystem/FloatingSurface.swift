import SwiftUI

extension View {
    /// Schwebende Flächen (z. B. Kochmodus-Steuerung): Liquid Glass ab iOS 26, sonst Material-Fallback.
    func floatingSurface(cornerRadius: CGFloat = Radius.lg) -> some View {
        modifier(FloatingSurfaceModifier(cornerRadius: cornerRadius))
    }
}

private struct FloatingSurfaceModifier: ViewModifier {
    let cornerRadius: CGFloat

    func body(content: Content) -> some View {
        if #available(iOS 26, *) {
            content.glassEffect(.regular, in: .rect(cornerRadius: cornerRadius))
        } else {
            content.background(.regularMaterial, in: .rect(cornerRadius: cornerRadius))
        }
    }
}
