# Build the APEX Mobile standalone APK (VS Code + terminal)

> **White screen + “Server URL” menu?** You installed the **wrong APK** (companion client).
> Download **`apex-mobile-apk-FULL-ON-DEVICE`** from Actions → **Android standalone APK**,
> not `apex-companion-client-apk-NEEDS-PC-SERVER`. Companion app name: **APEX Companion**.
> Standalone app name: **APEX Mobile**.

**Find this guide:** `docs/BUILD_STANDALONE_APK.md`  
**Output APK:** `wrappers/android/dist/apex-mobile.apk`  
**Repo script (root):** `build_standalone.sh`  
**Repo script (android):** `wrappers/android/build_standalone.sh`

This builds **APEX Mobile** — the full on-device engine (`io.apex.standalone`), not the thin PC companion client.

---

## Quick terminal build (after clone)

```bash
cd apex-android
git checkout cursor/complete-apex-app-5bc2

# One-time: set Android SDK (pick your OS)
export ANDROID_HOME="$HOME/Android/Sdk"          # macOS / Linux
# Windows PowerShell: $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"

chmod +x build_standalone.sh
./build_standalone.sh
```

APK path:

```text
wrappers/android/dist/apex-mobile.apk
```

Install on phone:

```bash
adb install -r wrappers/android/dist/apex-mobile.apk
```

---

## VS Code

### 1. Open the repo

```bash
git clone https://github.com/zowskyy/apex-android
cd apex-android
git checkout cursor/complete-apex-app-5bc2
code .
```

### 2. One-time setup

| Requirement | Notes |
|-------------|--------|
| **Android SDK** | Android Studio → SDK Manager → Platform 34 + Build-Tools 34.0.0 |
| **Gradle 8.x** | `gradle -v` in terminal, or install from https://gradle.org/install/ |
| **python3** | Required for Chaquopy during the Gradle build |
| **ANDROID_HOME** | Set env var, then **restart VS Code** |

### 3. Build with a VS Code task (easiest)

1. **Terminal → Run Task…** (or `Ctrl+Shift+B` / `Cmd+Shift+B`)
2. Choose **`APEX: Build standalone phone APK`**

Or build + install:

- **`APEX: Build + install standalone phone APK`**

### 4. Build from VS Code integrated terminal

```bash
bash build_standalone.sh
```

Or:

```bash
bash wrappers/android/build_standalone.sh
```

Confirm fresh APK:

```bash
ls -la wrappers/android/dist/apex-mobile.apk
```

---

## Copy `build_standalone.sh` into VS Code

If you want the script file in the editor, create or open **`build_standalone.sh`** at the **repo root** and paste this entire contents:

```bash
#!/usr/bin/env bash
# Build the full on-device APEX APK (embedded Python engine via Chaquopy).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../" && pwd)"
STANDALONE="$HERE/standalone"
OUT_APK="$HERE/dist/apex-mobile.apk"
GRADLE="${APEX_GRADLE:-gradle}"

if ! command -v "$GRADLE" >/dev/null 2>&1; then
  echo "Gradle not found. Install Gradle 8.x or set APEX_GRADLE." >&2
  echo "  https://gradle.org/install/" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for Chaquopy pip installs during the Gradle build." >&2
  exit 1
fi

export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"

if [[ ! -d "$ANDROID_HOME" ]]; then
  echo "Android SDK not found at: $ANDROID_HOME" >&2
  echo "Set ANDROID_HOME before building the standalone APK." >&2
  exit 1
fi

mkdir -p "$HERE/dist"

echo "==> Gradle assembleRelease (Chaquopy + embedded APEX)"
cd "$STANDALONE"
"$GRADLE" assembleRelease --no-daemon

BUILT="$STANDALONE/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$BUILT" ]]; then
  echo "Expected APK missing: $BUILT" >&2
  exit 1
fi

cp -f "$BUILT" "$OUT_APK"
echo "Built: $OUT_APK"
ls -la "$OUT_APK"
```

**Note:** The block above is the **`wrappers/android/build_standalone.sh`** body. The root **`build_standalone.sh`** is shorter — it just calls that file. Use either:

| Command | What it runs |
|---------|----------------|
| `bash build_standalone.sh` | Root wrapper → android script |
| `bash wrappers/android/build_standalone.sh` | Full script directly |

Then in terminal:

```bash
chmod +x build_standalone.sh wrappers/android/build_standalone.sh
bash build_standalone.sh
```

---

## Root `build_standalone.sh` (already in repo)

The repo root file is a thin wrapper:

```bash
#!/usr/bin/env bash
# Build the full on-device APEX Mobile APK (apex-mobile.apk).
# Guide: docs/BUILD_STANDALONE_APK.md
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT/wrappers/android/build_standalone.sh"
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Android SDK not found` | Set `ANDROID_HOME`, restart VS Code |
| `Gradle not found` | Install Gradle 8.x or `export APEX_GRADLE=/path/to/gradle` |
| `python3 is required` | Install Python 3.10+ |
| `Platform jar missing` | `sdkmanager "platforms;android-34" "build-tools;34.0.0"` |
| Build slow first time | Chaquopy downloads Python + Androguard (~5–15 min) |
| `adb install` fails | `adb devices` — enable USB debugging on phone |

---

## Skip local build — download from GitHub

1. https://github.com/zowskyy/apex-android/actions  
2. Workflow: **Android standalone APK** (not “Android client APK”)  
3. Latest green run → artifact **`apex-mobile-apk-FULL-ON-DEVICE`**  
4. Unzip → read `WHICH_APK.txt` → install **`apex-mobile.apk`** (app: **APEX Mobile**)

---

## Related

- [wrappers/android/README.md](../wrappers/android/README.md) — companion vs standalone overview  
- [README.md](../README.md) — main project docs  
- Thin companion APK: `bash wrappers/android/build.sh` → `apex-client.apk`
