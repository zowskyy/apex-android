# APEX Companion (Android)

A policy-aware Android companion for the APEX desktop workstation.

This is real, buildable source — not a placeholder. It ships with APEX because
device-side inspection is part of the complete product, not an add-on.

## What it does

- Lists apps the user can actually launch, using the narrow
  `<queries>` + `ACTION_MAIN`/`CATEGORY_LAUNCHER` visibility model
- Shows package name, version, install/update time, and APK paths
- Exports a selected app's APK set to shared storage so it can be moved to the
  desktop workstation for full APEX analysis
- Computes SHA-256 for each exported artifact so desktop analysis can verify
  it received exactly what the device held

## Package visibility posture

The companion deliberately does **not** request `QUERY_ALL_PACKAGES`.

Google Play treats the installed-app inventory as personal and sensitive data
and restricts broad visibility to a narrow set of core purposes. APEX's product
principle is to give the user full capability without pushing them into a
privacy-hostile or policy-fragile posture, so the companion uses launcher-intent
visibility, which covers the apps a user actually interacts with.

For complete device coverage — including system and non-launchable packages —
use the desktop ADB path (`apex device sync`), which operates on a device the
user has explicitly authorized.

## Build

```bash
cd tools/companion
./gradlew :app:assembleDebug
```

Output: `app/build/outputs/apk/debug/app-debug.apk`

Install on a connected device:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Privacy

- No network permission is declared; the app cannot transmit anything
- No analytics, no telemetry, no background collection
- Export is user-initiated per app
