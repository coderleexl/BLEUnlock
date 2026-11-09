# Local source debug build

This checkout starts from upstream BLEUnlock 1.12.2, commit
`c33a132f9b65ecd8fd55954a5e097a77b86c8a92`.

All main Swift/C code and the Objective-C login launcher are compiled locally.
The machine has Command Line Tools, not full Xcode, so `scripts/build_local.py`
reuses compiled nib/image resources from an existing BLEUnlock app. It does not
reuse the main or launcher executable. Full source XIB/asset compilation with
Xcode has not been verified on this machine.

## Build

Requires macOS on Apple Silicon, CLT with Swift, and an existing BLEUnlock app
as the resource source. The output must not already exist.

```sh
python3 scripts/build_local.py \
  --resources-from /Applications/BLEUnlock.app \
  --output /absolute/path/to/new/BLEUnlock.app \
  --log-path /absolute/path/to/bleunlock-runtime.jsonl
```

The app is ad-hoc signed for local debugging. macOS may request Bluetooth or
Accessibility permissions again when the executable identity changes; the
user must handle those prompts. No protection or permission database is
modified by this project.

`SourceBuild.json` inside the app records the base commit and source-file
hashes. The adjacent `.build.json` also records the final signed executable's
SHA-256; it is external to avoid a recursive signature/hash dependency.

## Diagnostic launch

```sh
/Applications/BLEUnlock.app/Contents/MacOS/BLEUnlock --diagnostics-only
```

This flag suppresses password reads/prompts, Accessibility setup, desktop
locking/unlocking, and injected password key events. Radio discovery and
monitoring follow the upstream code, with JSONL instrumentation added.
Launching without this flag restores upstream desktop behavior, including
password setup. Automatic unlock has not been validated in this build.

## Controlled hardware reproduction

```sh
/Applications/BLEUnlock.app/Contents/MacOS/BLEUnlock \
  --diagnostics-only --diagnostic-watch 'OPPO Watch X F302'
```

This debugging scenario filters discovery to the exact named watch, opens the
device-list scan path, waits 1.5 seconds after creating a list entry, then
calls the upstream monitor-selection path and closes the list. It does not
save the temporary selected UUID in preferences. After the watch radio is
restarted manually, it can capture whether the list's expiry timer cancels
the newly selected device. Check `state_before_selection` to establish
whether connection preceded selection.

Exact name matching is a test fixture only. It is not device authentication
and is unavailable unless `--diagnostics-only` is also supplied. It cannot
authorize a desktop unlock.

Useful event names:

- `monitor_start`: cached device state and UUID at selection.
- `peripheral_connected`: whether the callback's peripheral is the monitored reference.
- `scan_record_expired`: selected UUID/reference flags at list expiry.
- `cancel_connection`: exact call-site reason before cancellation.
- `peripheral_rssi_callback`, `monitor_rssi`: connected RSSI data.
- `signal_timeout`: whether a peripheral was ever acquired.
- `desktop_action_suppressed`: diagnosis-mode guard reached.

## Regression checks

```sh
python3 scripts/run_diagnostic_tests.py
```

This compiles the real application method bodies into a separate test app,
excluding only the `@NSApplicationMain` entry point. A real temporary event
script detects accidental process execution, and real `Device` / menu callbacks
exercise discovery-name matching. The test app has its own bundle identifier
and cleans up its script fixture. It does not lock the desktop or read passwords.

The repository has no upstream test suite. This local suite covers the new
diagnostic isolation and selection behavior; it does not emulate the watch's
radio or establish the cause of a real disconnect.

Existing upstream connection/identity bugs remain intentionally present until
the instrumented baseline establishes the precise branch. A successful build
or radio connection does not establish secure automatic unlock.
