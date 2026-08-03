# APEX on Android

**Build standalone APK (VS Code + terminal):** [docs/BUILD_STANDALONE_APK.md](../../docs/BUILD_STANDALONE_APK.md)

Two APK builds — pick the one that matches how you want to work.

| APK | Build | Role |
|-----|-------|------|
| **`apex-mobile.apk`** | `build_standalone.sh` / Gradle | **Full on-device engine** — inspect, scan, decompile, Code Pilot offline |
| **`apex-client.apk`** | `build.sh` | **Thin companion** — UI only; PC runs `apex mobile` |

## Recommended: APEX Mobile (standalone)

Everything runs on your phone. Performance scales with your device (RAM/CPU tiers).
Optional **Settings → Desktop server** connects to a PC for extra throughput.

### Build in VS Code

1. Android SDK + Gradle 8.x + `python3` on your PATH
2. `export ANDROID_HOME="$HOME/Android/Sdk"` (restart VS Code)
3. **Terminal → Run Task → APEX: Build standalone phone APK**
4. Install: **APEX: Install standalone APK on phone (adb)**

Or terminal:

```bash
bash wrappers/android/build_standalone.sh
adb install -r wrappers/android/dist/apex-mobile.apk
```

Output: `wrappers/android/dist/apex-mobile.apk`  
Package: `io.apex.standalone`

### GitHub Actions artifact

**Actions → Android standalone APK →** download `apex-mobile-apk`.

### On-device tiers (automatic)

| Tier | Typical devices | Upload cap | Decompile cap |
|------|-----------------|------------|---------------|
| low | ≤4 GB RAM | 96 MB | 400 classes |
| medium | 4–8 GB | 192 MB | 1,200 classes |
| high | 8+ GB | 320 MB | 4,000 classes |

Desktop limits are higher. This is intentional — on-device APEX does not pretend to match a workstation.

### Optional desktop boost

1. On PC: `apex mobile` (companion server)
2. On phone: APEX Mobile → **Settings** → **Desktop server** → enter `http://YOUR_PC_IP:8765`

---

## Companion client (`apex-client.apk`)

Use when you **always** want analysis on a powerful PC and the phone is only a remote UI.

```bash
bash wrappers/android/build.sh
.venv/bin/apex mobile   # on PC, same Wi-Fi
```

See VS Code tasks **APEX: Build phone client APK**.

---

## VS Code tasks

| Task | Output |
|------|--------|
| APEX: Build standalone phone APK | `apex-mobile.apk` |
| APEX: Build phone client APK | `apex-client.apk` |
| APEX: Install standalone APK on phone (adb) | installs mobile APK |
| APEX: Start mobile server | PC companion mode |

---

## Test checklist (Galaxy / Android)

1. Install `apex-mobile.apk`
2. Accept disclaimer
3. Wait for “engine ready” (first launch may take ~30s)
4. Choose APK from phone storage
5. Confirm manifest, security scan, class explorer
6. Try decompile (may be slower / capped vs desktop)
7. Optional: switch to desktop server in Settings
