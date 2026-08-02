#!/usr/bin/env bash
# Confirm GitHub Actions CI succeeded for the current branch HEAD commit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="${1:-$(git branch --show-current)}"
REPO="${GITHUB_REPOSITORY:-zowskyy/apex-android}"
HEAD="$(git rev-parse HEAD)"

if ! command -v gh >/dev/null 2>&1; then
  echo "check_github_ci: gh CLI not installed — verify CI manually on GitHub Actions" >&2
  exit 1
fi

echo "Checking CI for $REPO branch=$BRANCH commit=$HEAD"

SUCCESS_URL="$(gh run list --repo "$REPO" --branch "$BRANCH" --limit 20 \
  --json conclusion,headSha,url,workflowName \
  --jq "[.[] | select(.headSha==\"$HEAD\") | select(.workflowName==\"CI\") | select(.conclusion==\"success\")][0].url // empty")"

if [[ -z "$SUCCESS_URL" ]]; then
  echo "FAIL: no successful GitHub Actions CI run for this commit." >&2
  echo "Recent runs on $BRANCH:" >&2
  gh run list --repo "$REPO" --branch "$BRANCH" -L 5
  exit 1
fi

echo "PASS: GitHub CI succeeded — $SUCCESS_URL"
