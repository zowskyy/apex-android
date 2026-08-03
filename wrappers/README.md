# APEX wrappers — run APEX on any system

APEX ships launchers for every common platform. Pick the row that matches your setup.

| You are on | You want | Wrapper |
|------------|----------|---------|
| **Windows** | Local GUI | Double-click `wrappers/windows/apex-gui.bat` or Desktop `APEX.bat` after `install.ps1` |
| **Windows** | Phone access | `apex-mobile.bat` or `powershell wrappers/windows/apex.ps1 mobile` |
| **macOS** | Local GUI | Double-click `wrappers/macos/apex-gui.command` or `APEX.app` |
| **macOS** | Phone access | `apex-mobile.command` or `APEX Mobile.app` |
| **Linux** | Local GUI | `wrappers/linux/apex-gui.sh` or menu entry after `install.sh` |
| **Linux** | Phone access | `wrappers/linux/apex-mobile.sh` |
| **Android phone** | Control APEX on PC | Install `wrappers/android/dist/apex-client.apk` (build with `build.sh`) |
| **iPhone / iPad** | Browser UI | Safari → URL from `apex mobile` → Add to Home Screen ([ios/README.md](ios/README.md)) |
| **Any OS** | Container | `wrappers/docker/run.sh` → open `:8765` |
| **Any OS** | CLI only | `pip install -e .` then `apex` |

## Quick install

### Linux / macOS

```bash
bash wrappers/install.sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File wrappers\install.ps1
```

## Phone + computer workflow

1. **Computer:** `apex mobile` (or `APEX Mobile.bat` / `.app`)
2. **Phone browser:** open `http://<your-pc-ip>:8765` and upload APK
3. **Android app (optional):** build and install the WebView client:

```bash
bash wrappers/android/build.sh
adb install -r wrappers/android/dist/apex-client.apk
```

Open the app → **Server URL** → enter the same `http://IP:8765` address.

## Docker (server / homelab)

```bash
cd wrappers/docker
./run.sh
# Phone or PC: http://<host>:8765
```

## Build macOS `.app` bundles

```bash
bash wrappers/macos/create-apps.sh
open wrappers/macos/dist/APEX.app
```

## Notes

- Wrappers auto-create `.venv` and install `apex-android` on first run.
- **Mobile mode** listens on all interfaces (`0.0.0.0`) — trusted Wi-Fi only.
- Native Rust extensions require Rust + maturin (install script tries to build them).
