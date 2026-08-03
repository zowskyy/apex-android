#!/usr/bin/env bash
# Audit a release tag against mobile-hard-gate skill (.cursor/skills/mobile-hard-gate/SKILL.md)
#
# Usage:
#   scripts/audit_mobile_hard_gate.sh [tag]   # default: latest gh release tag
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  TAG="$(gh release view --repo "${GITHUB_REPOSITORY:-zowskyy/apex-android}" --json tagName -q .tagName 2>/dev/null || true)"
fi
if [[ -z "$TAG" ]]; then
  echo "audit_mobile_hard_gate: no tag and no latest release" >&2
  exit 1
fi

SHA="$(git rev-parse "${TAG}^{commit}")"
REPO="${GITHUB_REPOSITORY:-zowskyy/apex-android}"
BRANCH="$(git branch -r --contains "$SHA" | head -1 | sed 's/^[* ]*origin\///' || echo unknown)"

pass=0
fail=0
skip=0
manual=0

ok() { echo "  PASS  $*"; pass=$((pass + 1)); }
bad() { echo "  FAIL  $*" >&2; fail=$((fail + 1)); }
note() { echo "  NOTE  $*"; }
manual() { echo "  MANUAL $*"; manual=$((manual + 1)); }

echo "==> Mobile Hard Gate audit — $TAG ($SHA)"
echo ""

# --- Section 1: Chaquopy / embedded Python ---
echo "## 1. Two Python worlds"
if grep -q 'markupsafe' wrappers/android/standalone/app/build.gradle; then ok "build.gradle lists markupsafe"; else bad "markupsafe missing from build.gradle"; fi
if [[ -f wrappers/android/standalone/app/src/main/python/mutf8/mutf8.py ]]; then ok "vendored mutf8 shim present"; else bad "mutf8 shim missing"; fi
if [[ -x scripts/smoke_android_engine_imports.sh ]]; then ok "smoke_android_engine_imports.sh exists"; else bad "smoke script missing"; fi
if grep -q smoke_android_engine_imports.sh wrappers/android/build_standalone.sh; then ok "build_standalone.sh runs smoke test"; else bad "smoke not wired into build"; fi
if .venv/bin/pytest -q tests/test_android_chaquopy_deps.py >/dev/null 2>&1; then ok "test_android_chaquopy_deps.py"; else bad "Chaquopy manifest tests failed"; fi

# --- Section 2: WebView ---
echo "## 2. WebView wiring"
if grep -q onShowFileChooser wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java; then ok "onShowFileChooser implemented"; else bad "onShowFileChooser missing"; fi
if grep -q onActivityResult wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java; then ok "onActivityResult for file URIs"; else bad "onActivityResult missing"; fi
if grep -q setAllowContentAccess wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java; then ok "setAllowContentAccess enabled"; else bad "setAllowContentAccess missing"; fi
if grep -q 'drop.addEventListener("click"' apex/web.py; then ok "drop zone tap triggers file input"; else bad "mobile drop click handler missing"; fi
manual "Choose APK → picker → upload → analyze on real device"

# --- Section 3: Containers ---
echo "## 3. ZIP / XAPK containers"
if grep -q resolve_android_package apex/analysis.py; then ok "resolve_android_package() in analysis.py"; else bad "resolve_android_package missing"; fi
if grep -q container_note apex/web.py; then ok "UI container_note support"; else bad "container_note missing in web UI"; fi
if grep -q 'No DEX in this file' apex/web.py; then ok "0 DEX warning in UI"; else bad "0 DEX warning missing"; fi
if .venv/bin/pytest -q tests/test_package_resolve.py >/dev/null 2>&1; then ok "test_package_resolve.py"; else bad "package resolve tests failed"; fi

# --- Section 4: GitHub Actions ---
echo "## 4. GitHub Actions hard gate (commit $SHA)"
ci_url="$(gh run list --repo "$REPO" --json conclusion,headSha,workflowName,url \
  --jq "[.[] | select(.headSha==\"$SHA\") | select(.workflowName==\"CI\") | select(.conclusion==\"success\")][0].url // empty" 2>/dev/null || true)"
apk_url="$(gh run list --repo "$REPO" --json conclusion,headSha,workflowName,url \
  --jq "[.[] | select(.headSha==\"$SHA\") | select(.workflowName==\"Android standalone APK\") | select(.conclusion==\"success\")][0].url // empty" 2>/dev/null || true)"
rel_url="$(gh run list --repo "$REPO" --json conclusion,headSha,workflowName,url \
  --jq "[.[] | select(.headSha==\"$SHA\") | select(.workflowName==\"Release\") | select(.conclusion==\"success\")][0].url // empty" 2>/dev/null || true)"

if [[ -n "$ci_url" ]]; then ok "CI green — $ci_url"; else bad "CI not green on release commit"; fi
if [[ -n "$apk_url" ]]; then ok "Android standalone APK green — $apk_url"; else bad "Android standalone APK not green on release commit"; fi
if [[ -n "$rel_url" ]]; then ok "Release workflow green — $rel_url"; else bad "Release workflow not green on tag commit"; fi

# --- Section 5: Device smoke ---
echo "## 5. Device smoke (manual)"
manual "Install APEX-Mobile-$TAG.apk from Releases"
manual "First launch engine + notifications"
manual "Choose APK + analyze real APK"
manual "ZIP with nested APK or clear error"
manual "Decompile feedback"
manual "Settings → desktop remote (optional)"

# --- Section 6: Marketplace ---
echo "## 6. Marketplace readiness"
rel_json="$(gh release view "$TAG" --repo "$REPO" --json assets,url 2>/dev/null || echo '{}')"
ver="${TAG#v}"
for asset in "APEX-Mobile-${ver}.apk" "APEX-Mobile-${ver}.aab" "APEX-${ver}-windows-x64.zip" "APEX-${ver}-macos.zip" "APEX-${ver}-linux-x64.tar.gz"; do
  if echo "$rel_json" | jq -e --arg a "$asset" '.assets[]? | select(.name==$a)' >/dev/null 2>&1; then ok "release asset $asset"; else bad "missing release asset $asset"; fi
done
py_ver="$(grep '^__version__' apex/version.py | head -1)"
gradle_ver="$(grep versionName wrappers/android/standalone/app/build.gradle | head -1)"
if echo "$py_ver" | grep -q "$ver"; then ok "apex/version.py matches $TAG"; else bad "version.py mismatch: $py_ver"; fi
if echo "$gradle_ver" | grep -q "$ver"; then ok "build.gradle versionName matches $TAG"; else bad "build.gradle mismatch: $gradle_ver"; fi
if grep -q 'open_settings' wrappers/android/standalone/app/src/main/res/values/strings.xml; then ok "Settings menu string (not Server URL)"; else bad "open_settings string missing"; fi
if ! grep -q 'Server URL' wrappers/android/standalone/app/src/main/res/values/strings.xml 2>/dev/null; then ok "standalone strings omit Server URL"; else note "Server URL still in standalone strings — verify UX"; fi

echo ""
echo "==> Summary: PASS=$pass FAIL=$fail MANUAL=$manual (tag $TAG)"
if [[ "$fail" -gt 0 ]]; then
  echo "HARD GATE: NOT READY — fix FAIL items before mobile handoff." >&2
  exit 1
fi
echo "Automated hard gate: PASS (complete MANUAL device steps before declaring mobile done)."
exit 0
