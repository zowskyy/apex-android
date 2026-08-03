---
name: mobile-hard-gate
description: Mobile Hard Gate Build Check & Marketplace Readiness. Apply before shipping Android/iOS mobile apps, APK handoffs, or store releases. Requires device-relevant CI, runtime smoke tests, WebView/native wiring, and green GitHub Actions before any install link. Use on Cursor, Claude Code, and Claude mobile alongside finished-product-delivery.
---

# SKILL: Mobile Hard Gate Build Check & Marketplace Readiness

> **One rule:** A green **build** is not a green **product**. Mobile ships only
> when the **on-device runtime** matches what you advertise.

Use with `finished-product-delivery`. That skill covers scope, wiring, and CI in
general. **This skill adds the mobile hard gate** — the checks that only matter
when Python/JS runs inside WebView, Chaquopy, or native shells.

---

## 1. Two Python worlds (Android embedded)

Desktop CI (`pip install -e .`) pulls **full transitive dependencies**. Android
Chaquopy / embedded pip often uses **`--no-deps`** or a custom index.

| Check | Desktop CI | Mobile APK |
|-------|------------|------------|
| `import app` | Often passes | Can fail (`markupsafe`, `mutf8`, …) |
| Proof | `pytest` on host | **Post-build smoke on packaged env or APK** |

### Hard gate

- [ ] Every transitive dep for `import <engine>` is explicit in `build.gradle`
      / pip manifest **or** vendored pure-Python shim (no wheel on platform).
- [ ] `scripts/smoke_android_engine_imports.sh` (or equivalent) runs after
      `assembleRelease` and **fails the build** on structural/runtime gaps.
- [ ] Manifest test lists required packages (`tests/test_android_chaquopy_deps.py`
      or equivalent) — updated when imports change.

**Never** claim “engine works” from Gradle success alone.

---

## 2. WebView / native shell wiring

Web UIs that use `<input type="file">`, geolocation, camera, or downloads **do
not work** on Android WebView without native hooks.

### Hard gate

- [ ] `WebChromeClient.onShowFileChooser` implemented for file pickers.
- [ ] `onActivityResult` / Activity Result API returns URIs to WebView.
- [ ] `setAllowFileAccess` / `setAllowContentAccess` as needed.
- [ ] Tap targets: label + drop zone trigger the same picker on mobile.
- [ ] Manual smoke: **Choose file → picker opens → upload → analysis runs**.

Companion/thin clients and full standalone apps both need this if they host the
web UI in WebView.

---

## 3. Container formats (ZIP / XAPK / APKS)

Users pick `.zip` backups, XAPK bundles, and mislabeled archives — not only
`.apk`.

### Hard gate

- [ ] `resolve_android_package()` (or equivalent): extract nested `.apk` when
      root archive has no `classes*.dex`.
- [ ] UI shows **container note** (e.g. “Opened base.apk inside bundle.zip”).
- [ ] **0 DEX** → warning, not a success alert (“Decompiled 0 classes”).
- [ ] File input `accept` matches supported types; docs say APK vs ZIP.

---

## 4. GitHub Actions hard gate (before any handoff)

**No install link, no “download this APK”, no release tag for users** until:

```bash
scripts/check_github_ci.sh          # workflow CI green on HEAD
scripts/check_github_ci.sh --apk    # + Android standalone APK green on HEAD
```

For tagged releases:

- [ ] `Release` workflow **success** on tag commit.
- [ ] Artifacts on GitHub Releases match version in app (`versionName` / `__version__`).
- [ ] `apex-mobile.apk` is the **standalone** app (Settings, not “Server URL”).

Record the green run URL in PR / handoff notes.

Automated audit:

```bash
bash scripts/audit_mobile_hard_gate.sh v0.4.5   # or latest release tag
```

Exit code `0` = automated gates pass; **MANUAL** lines still require a real device.

---

## 5. Device smoke checklist (~15 minutes)

Automomation cannot replace this entirely. Run on **one real phone** before
calling mobile ready:

| Step | Pass |
|------|------|
| Install from **release APK** (not dev-only artifact) | ✓ |
| First launch: notifications, loading screen, engine starts | ✓ |
| **Choose APK** → system picker → file selected | ✓ |
| Analyze real `.apk` → DEX count > 0, manifest fields | ✓ |
| ZIP with nested APK → auto-resolve or clear error | ✓ |
| Decompile → classes > 0 or explicit “no DEX” message | ✓ |
| Settings → desktop remote (optional path) | ✓ |
| Uninstall old companion app if package/UX differs | ✓ |

Galaxy / mid-tier devices: expect **2–3 min** first-launch engine boot; UI must
say so.

---

## 6. Marketplace readiness (mobile store & Releases page)

### Release assets (minimum)

| Platform | Asset |
|----------|--------|
| Android | `APEX-Mobile-<ver>.apk` (+ optional `.aab`) |
| Windows | `*-windows-x64.zip` + `install.ps1` |
| macOS | `*-macos.zip` + `install.sh` |
| Linux | `*-linux-x64.tar.gz` + `install.sh` |
| iOS | No binary if browser-only — document Safari + Add to Home Screen |

### Listing fidelity

- [ ] App name in store/APK matches UI (“APEX”, not old companion name).
- [ ] Screenshots show **current** UI (engine banner, Settings menu).
- [ ] INSTALL.txt / release notes: first-launch wait, APK vs ZIP, optional PC boost.
- [ ] No “Server URL” companion flow advertised for standalone product.
- [ ] Version single-sourced (`version.py`, `build.gradle`, `pyproject.toml` aligned).

---

## 7. Anti-patterns (mobile)

| Anti-pattern | Hard gate response |
|--------------|-------------------|
| “CI green” = shippable mobile | Require `--apk` + device smoke |
| Gradle build only | Post-build import / APK bundle smoke |
| Hidden file input without `onShowFileChooser` | Native WebView wiring |
| Success alert for 0 classes / 0 DEX | Actionable warning |
| Hand user Actions artifact without release | Use Releases page + green tag |
| Desktop pytest covers mobile pip | Separate Chaquopy manifest tests |

---

## Definition of done (mobile)

Mobile is done when:

1. **Built** — standalone APK/AAB from green `Android standalone APK` on HEAD.
2. **Bundled** — structural/runtime smoke passed in CI.
3. **Wired** — WebView pickers, upload API, container resolution connected.
4. **Released** — GitHub Release (or explicit artifact) with install instructions.
5. **Smoked** — real device completed primary journey (pick APK → analyze).
6. **Honest** — release notes match app behavior and limitations.

**Do not hand users an APK because the archive compiled. Hand them an APK because
the engine ran on a phone.**
