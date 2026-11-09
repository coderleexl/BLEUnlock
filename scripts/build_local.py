#!/usr/bin/env python3
"""Compile all application code using CLT; reuse precompiled nib/image resources."""
import argparse
import hashlib
import json
import pathlib
import plistlib
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--resources-from', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--log-path', type=pathlib.Path)
args = parser.parse_args()
repo = pathlib.Path(__file__).resolve().parents[1]
source = repo / 'BLEUnlock'
app = args.output.resolve()
build = repo / '.build' / (app.stem + '-objects')
build.mkdir(parents=True, exist_ok=True)
if app.exists():
    raise SystemExit(f'Refusing to overwrite existing build: {app}')
resources = args.resources_from.resolve() / 'Contents' / 'Resources'
if not (resources / 'Base.lproj' / 'MainMenu.nib').exists():
    raise SystemExit(f'Compiled MainMenu.nib not found in {resources}')
sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
app.mkdir(parents=True)
contents = app / 'Contents'
(contents / 'MacOS').mkdir(parents=True)
shutil.copytree(resources, contents / 'Resources')


def run(command):
    print('+', ' '.join(str(x) for x in command), flush=True)
    subprocess.run([str(x) for x in command], cwd=repo, check=True)


common = ['-target', 'arm64-apple-macosx11.0', '-isysroot', sdk]
run(['xcrun', 'clang', *common, '-include', 'CoreFoundation/CoreFoundation.h',
     '-g', '-O0', '-c', source / 'lowlevel.c', '-o', build / 'lowlevel.o'])
run(['xcrun', 'swiftc', '-target', 'arm64-apple-macosx11.0', '-sdk', sdk,
     '-swift-version', '5', '-g', '-Onone', '-D', 'WATCH_DEBUG', '-module-name', 'BLEUnlock',
     '-import-objc-header', source / 'BLEUnlock-Bridging-Header.h',
     '-F', pathlib.Path(sdk) / 'System/Library/PrivateFrameworks',
     '-framework', 'MediaRemote', '-framework', 'login', '-framework', 'IOKit', '-lsqlite3',
     *sorted(source.glob('*.swift')), build / 'lowlevel.o',
     '-o', contents / 'MacOS/BLEUnlock'])
info = plistlib.loads((source / 'Info.plist').read_bytes())
info.update(CFBundleDevelopmentRegion='en', CFBundleExecutable='BLEUnlock',
            CFBundleIdentifier='jp.sone.BLEUnlock', CFBundleName='BLEUnlock',
            CFBundleVersion='796.20261109', LSMinimumSystemVersion='11.0',
            BLEUnlockSourceCommit=commit, BLEUnlockDiagnosticBuild=True)
if args.log_path:
    info['BLEUnlockDiagnosticLogPath'] = str(args.log_path.resolve())
(contents / 'Info.plist').write_bytes(plistlib.dumps(info))
(contents / 'PkgInfo').write_bytes(b'APPL????')

launcher = contents / 'Library/LoginItems/Launcher.app/Contents'
(launcher / 'MacOS').mkdir(parents=True)
old_launcher = args.resources_from.resolve() / 'Contents/Library/LoginItems/Launcher.app/Contents'
shutil.copytree(old_launcher / 'Resources', launcher / 'Resources')
run(['xcrun', 'clang', *common, '-fobjc-arc', '-g', '-O0', '-framework', 'Cocoa',
     repo / 'Launcher/main.m', repo / 'Launcher/AppDelegate.m', '-o', launcher / 'MacOS/Launcher'])
launcher_info = plistlib.loads((repo / 'Launcher/Info.plist').read_bytes())
launcher_info.update(CFBundleDevelopmentRegion='en', CFBundleExecutable='Launcher',
                     CFBundleIdentifier='jp.sone.BLEUnlock.Launcher', CFBundleName='Launcher',
                     LSMinimumSystemVersion='11.0')
(launcher / 'Info.plist').write_bytes(plistlib.dumps(launcher_info))
(launcher / 'PkgInfo').write_bytes(b'APPL????')
run(['codesign', '--force', '--sign', '-', str(launcher.parent)])
run(['codesign', '--force', '--sign', '-', '--entitlements',
     source / 'BLEUnlock.entitlements', app])
run(['codesign', '--verify', '--deep', '--strict', app])
source_hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for folder in [source, repo / 'Launcher']
                 for p in sorted(folder.iterdir()) if p.suffix in ['.swift', '.c', '.m', '.h']}
metadata = dict(source_commit=commit, target='arm64-apple-macosx11.0', sdk=sdk,
                resources_from=str(args.resources_from.resolve()),
                source_files_sha256=source_hashes,
                note='All executable code compiled locally; nib/image resources reused from release.')
(contents / 'Resources/SourceBuild.json').write_text(json.dumps(metadata, indent=2) + '\n')
# Metadata is part of the signed resource envelope.
run(['codesign', '--force', '--sign', '-', '--entitlements',
     source / 'BLEUnlock.entitlements', app])
run(['codesign', '--verify', '--deep', '--strict', app])
metadata['executable_sha256'] = hashlib.sha256((contents / 'MacOS/BLEUnlock').read_bytes()).hexdigest()
app.with_suffix('.build.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
