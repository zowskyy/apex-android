# APEX mobile test app

A real, minimal, installable, debuggable Android app — built with the actual
Android SDK toolchain (aapt2 + javac + d8 + zipalign + apksigner), not
synthetic bytes. Use this when you need a genuine APK to debug against: a
real binary-XML `AndroidManifest.xml`, real `resources.arsc`, real
`classes.dex` with actual bytecode (`MainActivity`, `BackgroundService`,
`BootReceiver`), real v2/v3 APK signature.

This is distinct from `tests/fixtures/sample_test.apk`
(`scripts/generate_test_apk.py`), which is ZIP-shaped with placeholder bytes
for the internal formats — good for zip_reader tests, but not installable or
launchable, and not useful once the arsc/manifest/dex parser slices (1.2,
1.3, 1.5+) need real binary formats to parse.

## Build

```bash
bash tools/mobile_test_app/build.sh
```

Requires the Android SDK (`build-tools;36.0.0`, `platforms;android-36.1`)
and a JDK; this repo's environment already has both (Android Studio's
bundled JBR is used automatically). Output: `tests/fixtures/apex_mobile_test.apk`
(gitignored — regenerate with the script, don't commit the binary).

A self-signed debug keystore (`debug.keystore`, gitignored) is generated on
first build.

## Install on a device/emulator to debug

```bash
adb install -r tests/fixtures/apex_mobile_test.apk
adb shell am start -n com.apex.testapp/.MainActivity
```

## Verify it's genuinely valid

```bash
"$LOCALAPPDATA/Android/Sdk/build-tools/36.0.0/apksigner.bat" verify --verbose tests/fixtures/apex_mobile_test.apk
"$LOCALAPPDATA/Android/Sdk/build-tools/36.0.0/aapt2.exe" dump badging tests/fixtures/apex_mobile_test.apk
```
