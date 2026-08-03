# APEX Mobile (Android)

**Build guide:** [docs/BUILD_STANDALONE_APK.md](../../docs/BUILD_STANDALONE_APK.md)

One app — **APEX** (`apex-mobile.apk`, package `io.apex.standalone`):

- **Default:** full reverse-engineering engine **on your phone** (offline)
- **Settings → Desktop computer:** remote access to a PC running `apex mobile` (extra speed)

## Build

```bash
bash build_standalone.sh
# → wrappers/android/dist/apex-mobile.apk
```

VS Code: **Run Task → APEX: Build standalone phone APK**

## GitHub artifact

Actions → **Android standalone APK** → `apex-mobile-apk`

## First launch

First open can take **2–3 minutes** while Python + Androguard load. Keep the app open.

## Settings

| Mode | When to use |
|------|-------------|
| **On this phone** | Offline, analyze APKs on device |
| **Desktop computer** | PC runs `apex mobile`, phone uses it over Wi‑Fi |

Desktop URL example: `http://192.168.1.42:8765`

## Device tiers (automatic)

Performance scales with RAM/CPU — not a bug, by design. Use desktop remote for huge APKs or heavy decompile.
