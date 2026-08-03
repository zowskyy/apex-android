#!/usr/bin/env bash
# Emergency rollback to a previous release version.
# Usage:
#   bash scripts/runbooks/rollback.sh 0.4.10
#   bash scripts/runbooks/rollback.sh 0.4.10 --dry-run
set -euo pipefail

TARGET="${1:?target version required e.g. 0.4.10}"
DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TAG="v${TARGET}"

echo "==> Rollback target: ${TAG}"

if $DRY_RUN; then
  echo "DRY RUN: would verify GitHub release assets for ${TAG}"
  echo "DRY RUN: would run scripts/release/check_version_sync.sh after sync_version.sh ${TARGET}"
  echo "DRY RUN: would create signed tag rollback-${TARGET}-$(date +%Y%m%d) and push"
  echo "DRY RUN: would notify team via configured webhook (APEX_ALERT_WEBHOOK)"
  exit 0
fi

if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "rollback: tag ${TAG} not found locally — fetch tags first" >&2
  exit 1
fi

bash "$ROOT/scripts/release/sync_version.sh" "$TARGET"
bash "$ROOT/scripts/release/check_version_sync.sh"

ROLLBACK_TAG="rollback-${TARGET}-$(date +%Y%m%d)"
git tag -s "$ROLLBACK_TAG" -m "Emergency rollback to ${TARGET}"
echo "Created tag ${ROLLBACK_TAG} — push with: git push origin ${ROLLBACK_TAG}"
