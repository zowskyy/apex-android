#!/usr/bin/env bash
# Confirm GitHub Actions succeeded for the current branch HEAD commit.
#
# Usage:
#   scripts/check_github_ci.sh              # CI workflow only
#   scripts/check_github_ci.sh --apk        # CI + Android standalone APK (required before shipping mobile)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHECK_APK=0
BRANCH="${GITHUB_HEAD_REF:-$(git branch --show-current)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apk|--mobile) CHECK_APK=1 ;;
    -h|--help)
      sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      BRANCH="$1"
      ;;
  esac
  shift
done

REPO="${GITHUB_REPOSITORY:-zowskyy/apex-android}"
HEAD="$(git rev-parse HEAD)"

if ! command -v gh >/dev/null 2>&1; then
  echo "check_github_ci: gh CLI not installed — verify CI manually on GitHub Actions" >&2
  exit 1
fi

check_workflow() {
  local workflow_name="$1"
  local url
  url="$(gh run list --repo "$REPO" --branch "$BRANCH" --limit 30 \
    --json conclusion,headSha,url,workflowName \
    --jq "[.[] | select(.headSha==\"$HEAD\") | select(.workflowName==\"$workflow_name\") | select(.conclusion==\"success\")][0].url // empty")"
  if [[ -z "$url" ]]; then
    echo "FAIL: no successful '$workflow_name' run for commit $HEAD on branch $BRANCH" >&2
    gh run list --repo "$REPO" --branch "$BRANCH" -L 8 \
      --json conclusion,workflowName,headSha,url,createdAt \
      --jq ".[] | select(.headSha==\"$HEAD\") | \"  \(.conclusion) \(.workflowName) \(.url)\""
    return 1
  fi
  echo "PASS: $workflow_name — $url"
  return 0
}

echo "Checking GitHub Actions for $REPO branch=$BRANCH commit=$HEAD"

FAIL=0
check_workflow "CI" || FAIL=1
if [[ "$CHECK_APK" -eq 1 ]]; then
  check_workflow "Android standalone APK" || FAIL=1
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "" >&2
  echo "Do not ship artifacts or tell users to download until the above workflows are green on HEAD." >&2
  exit 1
fi

echo "All required workflows passed on HEAD."
