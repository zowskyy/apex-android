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
VER="${TAG#v}"

pass=0
fail=0
manual=0

ok() { echo "  PASS  $*"; pass=$((pass + 1)); }
bad() { echo "  FAIL  $*" >&2; fail=$((fail + 1)); }
note() { echo "  NOTE  $*"; }
manual_step() { echo "  MANUAL $*"; manual=$((manual + 1)); }

at_tag() {
  git show "${SHA}:$1" 2>/dev/null
}

at_tag_grep() {
  at_tag "$1" | grep -q "$2"
}

echo "==> Mobile Hard Gate audit — $TAG ($SHA)"
echo ""

echo "## 1. Two Python worlds"
if at_tag_grep wrappers/android/standalone/app/build.gradle markupsafe; then ok "build.gradle lists markupsafe"; else bad "markupsafe missing from build.gradle"; fi
if git cat-file -e "${SHA}:wrappers/android/standalone/app/src/main/python/mutf8/mutf8.py" 2>/dev/null; then ok "vendored mutf8 shim present"; else bad "mutf8 shim missing"; fi
if git cat-file -e "${SHA}:scripts/smoke_android_engine_imports.sh" 2>/dev/null; then ok "smoke_android_engine_imports.sh present"; else bad "smoke script missing"; fi
if at_tag_grep wrappers/android/build_standalone.sh smoke_android_engine_imports.sh; then ok "build_standalone.sh runs smoke test"; else bad "smoke not wired into build"; fi
if .venv/bin/pytest -q tests/test_android_chaquopy_deps.py >/dev/null 2>&1; then ok "test_android_chaquopy_deps.py (current tree)"; else bad "Chaquopy manifest tests failed"; fi

echo "## 2. WebView wiring"
if at_tag_grep wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java onShowFileChooser; then ok "onShowFileChooser implemented"; else bad "onShowFileChooser missing"; fi
if at_tag_grep wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java onActivityResult; then ok "onActivityResult for file URIs"; else bad "onActivityResult missing"; fi
if at_tag_grep wrappers/android/standalone/app/src/main/java/io/apex/standalone/MainActivity.java setAllowContentAccess; then ok "setAllowContentAccess enabled"; else bad "setAllowContentAccess missing"; fi
if at_tag_grep apex/web.py 'drop.addEventListener("click"'; then ok "drop zone tap triggers file input"; else bad "mobile drop click handler missing"; fi
manual_step "Choose APK → picker → upload → analyze on real device"

echo "## 3. ZIP / XAPK containers"
if at_tag_grep apex/analysis.py resolve_android_package; then ok "resolve_android_package() in analysis.py"; else bad "resolve_android_package missing"; fi
if at_tag_grep apex/web.py container_note; then ok "UI container_note support"; else bad "container_note missing in web UI"; fi
if at_tag_grep apex/web.py 'No DEX in this file'; then ok "0 DEX warning in UI"; else bad "0 DEX warning missing"; fi
if .venv/bin/pytest -q tests/test_package_resolve.py >/dev/null 2>&1; then ok "test_package_resolve.py (current tree)"; else bad "package resolve tests failed"; fi

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

echo "## 5. Device smoke (manual)"
manual_step "Install APEX-Mobile-${VER}.apk from Releases"
manual_step "First launch engine + notifications"
manual_step "Choose APK + analyze real APK"
manual_step "ZIP with nested APK or clear error"
manual_step "Decompile feedback"
manual_step "Settings → desktop remote (optional)"

echo "## 6. Marketplace readiness"
rel_json="$(gh release view "$TAG" --repo "$REPO" --json assets,url 2>/dev/null || echo '{}')"
for asset in "APEX-Mobile-${VER}.apk" "APEX-Mobile-${VER}.aab" "APEX-${VER}-windows-x64.zip" "APEX-${VER}-macos.zip" "APEX-${VER}-linux-x64.tar.gz"; do
  if echo "$rel_json" | jq -e --arg a "$asset" '.assets[]? | select(.name==$a)' >/dev/null 2>&1; then ok "release asset $asset"; else bad "missing release asset $asset"; fi
done
py_ver="$(at_tag apex/version.py | grep '^__version__' | head -1 || true)"
gradle_ver="$(at_tag wrappers/android/standalone/app/build.gradle | grep versionName | head -1 || true)"
toml_ver="$(at_tag pyproject.toml | grep '^version' | head -1 || true)"
if echo "$py_ver" | grep -q "$VER"; then ok "apex/version.py matches $TAG — $py_ver"; else bad "version.py mismatch at tag: $py_ver"; fi
if echo "$gradle_ver" | grep -q "$VER"; then ok "build.gradle versionName matches $TAG"; else bad "build.gradle mismatch at tag: $gradle_ver"; fi
if echo "$toml_ver" | grep -q "$VER"; then ok "pyproject.toml matches $TAG"; else bad "pyproject.toml mismatch at tag: $toml_ver"; fi
if at_tag_grep wrappers/android/standalone/app/src/main/res/values/strings.xml open_settings; then ok "Settings menu string (not Server URL)"; else bad "open_settings string missing"; fi
if ! at_tag wrappers/android/standalone/app/src/main/res/values/strings.xml | grep -q 'Server URL'; then ok "standalone strings omit Server URL"; else note "Server URL still in standalone strings — verify UX"; fi

echo ""
echo "==> Summary: PASS=$pass FAIL=$fail MANUAL=$manual (tag $TAG)"
if [[ "$fail" -gt 0 ]]; then
  echo "HARD GATE: NOT READY — fix FAIL items before mobile handoff." >&2
  exit 1
fi
echo "Automated hard gate: PASS (complete MANUAL device steps before declaring mobile done)."
exit 0
