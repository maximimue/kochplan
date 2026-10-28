import SwiftUI

enum Spacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
}

enum Radius {
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 20
}

enum AppColor {
    static let cardBackground = Color(.secondarySystemBackground)
}

enum AppFont {
    static let sectionTitle = Font.title3.weight(.semibold)
    static let metric = Font.subheadline.weight(.medium)
}
