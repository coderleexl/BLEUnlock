# BLEUnlock Source Debug Build Implementation Plan

> Execution: native, in this freshly cloned checkout. The user explicitly requested source download, local build, precise debugging, and replacement of the installed release; proceed within that scope.

**Goal:** Build BLEUnlock 1.12.2 from source, capture exact connection/cancellation decisions, and replace the existing Homebrew release after the build runs.

**Architecture:** Keep the existing Swift/C application and CoreBluetooth behavior for initial reproduction. Add JSONL diagnostics at lifecycle, monitoring, timer, connection, RSSI, and cancellation boundaries. A command-line diagnostics-only launch suppresses password access and desktop lock/unlock actions during radio investigation.

**Tech Stack:** Swift 5 language mode, Swift/Clang command-line toolchain, AppKit, CoreBluetooth, SQLite3, IOKit, login and MediaRemote frameworks.

**Spec:** User request in this chat (download/build/debug/uninstall original) and `../../../../../outputs/macos-watch-diagnosis.md` (existing empirical observations).

## Global Constraints

- Navigate with targeted text searches and direct reads. Do not initialize CodeGraph.
- Baseline source: tag 1.12.2, commit c33a132f9b65ecd8fd55954a5e097a77b86c8a92.
- No full Xcode is installed. Compile all Swift/C and launcher Objective-C code with CLT; reuse the installed release's compiled nib/image resources, and disclose that limitation.
- Preserve the original bundle in scratch storage and retain preferences/keychain. Do not use Homebrew `--zap`.
- Do not log or retrieve login passwords during diagnostics.
- Do not automatically accept new macOS permission grants.

## Review Focus

- Resource reuse must never retain the release main executable; verify rebuilt executable hash and debug metadata.
- Diagnostics-only mode must suppress both automatic and manual lock/unlock actions, password reads/prompts, and accessibility event injection.
- Logging must not change timer or connection decisions during baseline reproduction.
- Termination must release diagnostic resources and leave only the intended app running.
- Do not declare UUID recovery or automatic unlock fixed based solely on a successful source build.

## Task 1: Reproducible CLT build

- [x] Add `scripts/build_local.py`: consume the existing release resources and emit an ARM64 app in a specified staging path; compile main and launcher from source and ad-hoc sign.
- [x] Build unchanged application source first; verify executable architecture, linked frameworks, and signatures.

## Task 2: Instrumented application

- [x] Add `BLEUnlock/DiagnosticLog.swift`: JSONL writer and diagnostics-only launch flag.
- [x] Instrument `BLE.swift` and `AppDelegate.swift` at monitor selection, discovery, timers, connection callbacks, RSSI, and each cancellation reason.
- [x] Add diagnosis-only guards at desktop action entry points and initial password/accessibility setup.
- [x] Build and launch; confirm app-start, central-state, monitored-UUID records, and no desktop actions.
- [ ] Reproduce on the attached watch when advertising is available; explicitly report any required physical radio reset.

## Task 3: Replace installed release

- [x] Preserve original release bundle and selected preferences metadata in scratch storage.
- [x] Once startup is verified, stop the release process and run `brew uninstall --cask bleunlock` without `--zap`.
- [x] Install source-built app at `/Applications/BLEUnlock.app`, run it in diagnostics-only mode, and verify running executable hash and log output.
- [ ] Export build instructions, runtime evidence, and a source patch under the workspace `outputs/` directory.

No speculative connection fix is included before the instrumented baseline establishes the exact branch. Compilation and real lifecycle/event checks validate this diagnostic-only change; do not add tests that merely assert log strings.

Review: a fresh reviewer found missing diagnostic guards around unlock-event scripts/media and inconsistent advertised-name matching. Real AppDelegate regression tests first reproduced 3 action-isolation failures, then one advertised-name-only selection failure; the corrected suite passes all 6 checks. One build/test run failed because both used the same C object file; build objects are now isolated per output and the test suite compiles its own C object. The hardware scenario is prepared and waits for a manual watch Bluetooth restart requested in chat.
