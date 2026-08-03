# APEX phone client APK

WebView shell that opens your PC’s `apex mobile` server. Use this to test APEX
on a Galaxy / Android phone without typing URLs every time.

## Fastest path: download APK from GitHub Actions

1. Open the repo on GitHub → **Actions** → **Android client APK**
2. Open the latest green run → **Artifacts** → download `apex-client-apk`
3. Unzip → copy `apex-client.apk` to your phone
4. On the phone: allow install from Files / Chrome → install APEX
5. On your PC (same Wi‑Fi):

   ```bash
   git checkout cursor/complete-apex-app-5bc2
   ./build.sh --skip-tests
   .venv/bin/apex mobile
   ```

6. In the APEX app → menu **Server URL** → enter `http://YOUR_PC_IP:8765`

Trigger a build yourself: **Actions → Android client APK → Run workflow**.

## VS Code (PC or Codespaces) — build + install

### One-time setup

1. Install [VS Code](https://code.visualstudio.com/)
2. Clone this branch:

   ```bash
   git clone https://github.com/zowskyy/apex-android
   cd apex-android
   git checkout cursor/complete-apex-app-5bc2
   code .
   ```

3. Install Android SDK command-line tools (or Android Studio) and set:

   ```bash
   export ANDROID_HOME="$HOME/Android/Sdk"   # Windows: %LOCALAPPDATA%\Android\Sdk
   ```

4. Install platform + build-tools:

   ```bash
   sdkmanager "platforms;android-34" "build-tools;34.0.0"
   ```

5. Plug in your phone with **USB debugging** on (Developer options).

### Build from VS Code

**Terminal → Run Task…** (or `Ctrl+Shift+B` / `Cmd+Shift+B`):

| Task | What it does |
|------|----------------|
| **APEX: Build phone client APK** | Runs `wrappers/android/build.sh` → `wrappers/android/dist/apex-client.apk` |
| **APEX: Install APK on phone (adb)** | `adb install -r` that APK |
| **APEX: Build + install phone APK** | Both, in order |
| **APEX: Start mobile server** | Starts `apex mobile` for the phone to hit |

Or in the integrated terminal:

```bash
bash wrappers/android/build.sh
ls -la wrappers/android/dist/apex-client.apk
adb devices
adb install -r wrappers/android/dist/apex-client.apk
```

## VS Code on Android (Termux / code-server)

Building a signed APK **on the phone** needs a full Android SDK + JDK — too heavy for most devices. Recommended:

1. Build or download the APK on a PC / GitHub Actions (above)
2. Use **VS Code on Android** only to edit code / open docs / SSH to a PC
3. Or use ADB over Wi‑Fi / USB from the PC: `adb install -r apex-client.apk`

If you still want Termux for the **server** side on another machine, run APEX there and point the client APK at that host’s IP.

## After install — end-to-end test checklist

1. PC: `apex mobile` → note `http://192.168.x.x:8765`
2. Phone + PC on same Wi‑Fi
3. Open APEX app → set Server URL
4. Tap **Choose APK** → pick any APK on the phone
5. Confirm metadata, security verdict, class search
6. Pro: try **Code Pilot** prompt (needs Pro license on the PC server)

## Output path

```text
wrappers/android/dist/apex-client.apk
```

Package id: `io.apex.client`
