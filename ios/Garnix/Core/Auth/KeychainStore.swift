import Foundation
import Security

/// Access-/Refresh-Token ausschließlich hier, nie in UserDefaults/SwiftData.
enum KeychainStore {
    private static var service: String { Bundle.main.bundleIdentifier ?? "Garnix" }

    static func save(_ value: String, forKey key: String) {
        let data = Data(value.utf8)
        SecItemDelete(query(key) as CFDictionary)
        var attributes = query(key)
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(attributes as CFDictionary, nil)
    }

    static func read(forKey key: String) -> String? {
        var attributes = query(key)
        attributes[kSecReturnData as String] = true
        attributes[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        guard SecItemCopyMatching(attributes as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(forKey key: String) {
        SecItemDelete(query(key) as CFDictionary)
    }

    private static func query(_ key: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
    }
}
