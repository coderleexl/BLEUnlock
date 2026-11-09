#!/usr/bin/env python3
"""Exercise actual AppDelegate action methods in an isolated test application."""
from pathlib import Path
import plistlib
import subprocess

repo = Path(__file__).resolve().parents[1]
source = repo / 'BLEUnlock'
root = repo / '.build/diagnostic-tests'
root.mkdir(parents=True, exist_ok=True)
app = root / 'DiagnosticTests.app'
contents = app / 'Contents'
(contents / 'MacOS').mkdir(parents=True, exist_ok=True)
info = dict(CFBundleIdentifier='dev.local.BLEUnlock.DiagnosticTests',
            CFBundleName='DiagnosticTests', CFBundleExecutable='DiagnosticTests',
            CFBundlePackageType='APPL', NSBluetoothAlwaysUsageDescription='Local diagnostic regression test.')
(contents / 'Info.plist').write_bytes(plistlib.dumps(info))
original = (source / 'AppDelegate.swift').read_text()
assert original.count('@NSApplicationMain\n') == 1
# Exclude only the application entry point; compile the real method bodies.
app_delegate = root / 'AppDelegate.swift'
app_delegate.write_text(original.replace('@NSApplicationMain\n', ''))
main = root / 'main.swift'
main.write_text(r'''
import Cocoa
import Darwin

func runTests() throws -> Int32 {
let app = NSApplication.shared
let delegate = AppDelegate()
var failures: [String] = []
func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    if condition() { print("PASS: \(message)") }
    else { failures.append(message); print("FAIL: \(message)") }
}
expect(DiagnosticLog.diagnosticsOnly, "test process is in diagnostics-only mode")

let fm = FileManager.default
let directory = try fm.url(for: .applicationScriptsDirectory, in: .userDomainMask,
                          appropriateFor: nil, create: true)
guard directory.lastPathComponent == "dev.local.BLEUnlock.DiagnosticTests" else {
    fatalError("Refusing to touch an unrelated scripts directory: \(directory)")
}
let script = directory.appendingPathComponent("event")
guard !fm.fileExists(atPath: script.path) else { fatalError("Test event fixture already exists") }
let sentinel = URL(fileURLWithPath: CommandLine.arguments[1])
guard !fm.fileExists(atPath: sentinel.path) else { fatalError("Test sentinel already exists") }
defer {
    try? fm.removeItem(at: script)
    try? fm.removeItem(at: sentinel)
    if (try? fm.contentsOfDirectory(atPath: directory.path).isEmpty) == true {
        try? fm.removeItem(at: directory)
    }
}
// This is a real executable fixture, not a mocked Process or an asserted log line.
try "#!/bin/sh\n/usr/bin/touch \"$1\"\n".write(to: script, atomically: true, encoding: .utf8)
try fm.setAttributes([.posixPermissions: 0o700], ofItemAtPath: script.path)
delegate.runScript(sentinel.path)
Thread.sleep(forTimeInterval: 0.4)
expect(!fm.fileExists(atPath: sentinel.path), "diagnostics must not execute event scripts")

delegate.manualLock = true
delegate.onUnlock()
expect(delegate.manualLock, "diagnostic unlock callback must not mutate desktop action state")
delegate.manualLock = false
delegate.lockNow()
expect(!delegate.manualLock, "diagnostic manual lock must not enter desktop action flow")

let unrelated = Device(uuid: UUID(uuidString: "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")!)
unrelated.advertisedName = "Unrelated Device"
delegate.newDevice(device: unrelated)
expect(!delegate.diagnosticSelectionScheduled, "unrelated device must not enter the watch scenario")
let advertisedOnly = Device(uuid: UUID(uuidString: "11111111-2222-3333-4444-555555555555")!)
advertisedOnly.advertisedName = "OPPO Watch X F302"
delegate.newDevice(device: advertisedOnly)
expect(delegate.diagnosticSelectionScheduled,
       "advertised-name-only watch must enter the controlled selection scenario")

print("\(failures.count) failures")
return failures.isEmpty ? 0 : 1
}
exit(try runTests())
''')
sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
subprocess.run(['xcrun', 'clang', '-target', 'arm64-apple-macosx11.0', '-isysroot', sdk,
                '-include', 'CoreFoundation/CoreFoundation.h', '-c', str(source / 'lowlevel.c'),
                '-o', str(root / 'lowlevel.o')], check=True)
command = ['xcrun', 'swiftc', '-target', 'arm64-apple-macosx11.0', '-sdk', sdk,
           '-swift-version', '5', '-Onone', '-module-name', 'BLEUnlock',
           '-import-objc-header', source / 'BLEUnlock-Bridging-Header.h',
           '-F', Path(sdk) / 'System/Library/PrivateFrameworks',
           '-framework', 'MediaRemote', '-framework', 'login', '-framework', 'IOKit', '-lsqlite3',
           *[p for p in sorted(source.glob('*.swift')) if p.name != 'AppDelegate.swift'],
           app_delegate, main, root / 'lowlevel.o', '-o', contents / 'MacOS/DiagnosticTests']
subprocess.run([str(x) for x in command], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
sentinel = root / 'unexpected-event-script-ran'
result = subprocess.run([str(contents / 'MacOS/DiagnosticTests'), str(sentinel), '--diagnostics-only',
                         '--diagnostic-watch', 'OPPO Watch X F302'])
raise SystemExit(result.returncode)
