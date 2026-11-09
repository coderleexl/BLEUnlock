import Foundation

/// Local source-build instrumentation. Never accepts credential values.
enum DiagnosticLog {
    static let diagnosticsOnly = ProcessInfo.processInfo.arguments.contains("--diagnostics-only")
    /// Controlled hardware reproduction only; never used as an unlock identity.
    static let watchName: String? = {
        let args = ProcessInfo.processInfo.arguments
        guard diagnosticsOnly, let index = args.firstIndex(of: "--diagnostic-watch"),
              args.indices.contains(index + 1), !args[index + 1].hasPrefix("--") else { return nil }
        return args[index + 1]
    }()
    static func matchesWatch(peripheralName: String?, advertisedName: String?) -> Bool {
        guard let name = watchName else { return false }
        return peripheralName == name || advertisedName == name
    }
    private static let enabled = Bundle.main.object(forInfoDictionaryKey: "BLEUnlockDiagnosticBuild") as? Bool ?? false
    private static let writeLock = NSLock()
    private static let formatter = ISO8601DateFormatter()
    static let path: String = {
        if let path = Bundle.main.object(forInfoDictionaryKey: "BLEUnlockDiagnosticLogPath") as? String {
            return path
        }
        let library = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
        return library.appendingPathComponent("Logs/BLEUnlock/diagnostic.jsonl").path
    }()
    private static let file: FileHandle? = {
        guard enabled else { return nil }
        let url = URL(fileURLWithPath: path)
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                                    withIntermediateDirectories: true, attributes: nil)
            if !FileManager.default.fileExists(atPath: path) {
                FileManager.default.createFile(atPath: path, contents: nil, attributes: [.posixPermissions: 0o600])
            }
            let handle = try FileHandle(forWritingTo: url)
            handle.seekToEndOfFile()
            return handle
        } catch {
            NSLog("BLEUnlock diagnostic log unavailable: %@", error.localizedDescription)
            return nil
        }
    }()

    static func event(_ event: String, _ fields: [String: Any] = [:]) {
        guard enabled else { return }
        writeLock.lock()
        defer { writeLock.unlock() }
        var record = fields
        record["event"] = event
        record["time"] = formatter.string(from: Date())
        record["uptime"] = ProcessInfo.processInfo.systemUptime
        record["pid"] = ProcessInfo.processInfo.processIdentifier
        guard let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]) else { return }
        file?.write(data)
        file?.write(Data([0x0a]))
    }

    static func suppressed(_ action: String) {
        event("desktop_action_suppressed", ["action": action, "diagnostics_only": true])
    }
}
