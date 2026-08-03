## APEX v0.4.11

**Complete APEX:** hard gate through CVE scanners, unified release CI, audit trail, and operational runbooks.

### Highlights

- **Hard gate (v0.4.11):** manifest, dex, security, secrets, native, api_watch, netsec, lint, obfuscation, dependency/CVE (advisory)
- **Audit trail:** hash-chained gate audit log + monthly compliance reports
- **Release factory:** `release.yml` DAG — core wheels → Android + desktop → gate verify → SBOM → publish + SHA256SUMS
- **Android:** Chaquopy symlink (dev) or wheel mode (`APEX_ENGINE_MODE=wheel`) for CI parity
- **Ops:** runbooks (CVE / rollback / version drift), `supply-chain.yml`, `emergency-rollback.yml`, `monitor-gates.yml`
- **CLI:** `apex update-db --osv` for optional OSV merge

### Install

Download the file for your platform below, then open `INSTALL.txt` inside the bundle.

| Platform | File | Install |
|----------|------|---------|
| **Android** | `APEX-Mobile-*.apk` | Install APK directly |
| **Android (AAB)** | `APEX-Mobile-*.aab` | Play Store / `bundletool` |
| **Windows** | `APEX-*-windows-x64.zip` | Run `install.ps1` |
| **macOS** | `APEX-*-macos.zip` | Run `bash install.sh` |
| **Linux** | `APEX-*-linux-x64.tar.gz` | Run `bash install.sh` |

Verify checksums: `sha256sum -c SHA256SUMS` (and `SHA256SUMS.asc` when GPG-signed).

### Android (APEX Mobile)

- App name: **APEX** — menu **Settings** (not “Server URL”).
- First launch: allow notifications, wait **2–3 minutes** on the loading screen.
- Optional PC boost: run `apex mobile` on your computer → **Settings → Desktop computer** on the phone.

### Desktop

After install: `apex doctor`, `apex gui`, or `apex mobile` for phone browser access.

### iOS

No binary — use Safari with your PC’s `apex mobile` URL and **Add to Home Screen**.

### Docs

- [MASTER_NOTES_COPYPASTE.md](https://github.com/zowskyy/apex-android/blob/cursor/complete-apex-app-5bc2/docs/MASTER_NOTES_COPYPASTE.md)
- [BLUEPRINT_GUIDE.md](https://github.com/zowskyy/apex-android/blob/cursor/complete-apex-app-5bc2/docs/BLUEPRINT_GUIDE.md)
