# Build APEX Mobile APK (VS Code + terminal)

**Output:** `wrappers/android/dist/apex-mobile.apk`  
**App on phone:** **APEX** (package `io.apex.standalone`)  
**Script:** `bash build_standalone.sh` (repo root)

APEX Mobile includes **on-device analysis** and **desktop remote access** (Settings → Desktop computer → URL from `apex mobile` on your PC).

---

## Quick build

```bash
git clone https://github.com/zowskyy/apex-android
cd apex-android
git checkout cursor/complete-apex-app-5bc2

export ANDROID_HOME="$HOME/Android/Sdk"   # Windows: %LOCALAPPDATA%\Android\Sdk

chmod +x build_standalone.sh
./build_standalone.sh
adb install -r wrappers/android/dist/apex-mobile.apk
```

---

## VS Code

1. Open repo in VS Code, set `ANDROID_HOME`, restart VS Code
2. **Terminal → Run Task → APEX: Build standalone phone APK**
3. **APEX: Install standalone APK on phone (adb)**

---

## Download (no build)

1. https://github.com/zowskyy/apex-android/actions
2. **Android standalone APK** workflow
3. Artifact: **apex-mobile-apk**
4. Install `apex-mobile.apk`

---

## Using the app

1. Accept disclaimer
2. Wait up to **3 minutes** on first launch (loading screen — not a white screen)
3. Choose APK → analyze on phone
4. **Menu → Settings → Desktop computer** to use a PC: run `apex mobile` on the computer, paste URL

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Stuck on loading | Wait 3 min first launch; check notification permission |
| Engine failed | Settings → Desktop computer + PC URL, or reinstall latest APK |
| Slow decompile | Normal on phone — use desktop remote for big jobs |
| `Gradle not found` | Install Gradle 8.x |
| `Android SDK not found` | Set `ANDROID_HOME` |

---

## `build_standalone.sh` (root)

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT/wrappers/android/build_standalone.sh"
```

Full Gradle/Chaquopy script: `wrappers/android/build_standalone.sh`
