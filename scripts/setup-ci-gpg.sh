#!/usr/bin/env bash
# One-time CI / maintainer GPG setup for signed tags and SHA256SUMS.
#
# GitHub Actions:
#   1. Export private key: gpg --armor --export-secret-keys KEYID > private.asc
#   2. Add repository secret GPG_PRIVATE_KEY (contents of private.asc)
#   3. Add GPG_KEY_ID secret (fingerprint or email)
#   4. Optional: GPG_PASSPHRASE if key is protected
#
# Local maintainer:
#   gpg --full-generate-key
#   git config commit.gpgsign true
#   git tag -s v0.4.11 -m "APEX v0.4.11"
set -euo pipefail

echo "==> APEX GPG setup guide"
echo ""
echo "Required GitHub secrets (Settings → Secrets → Actions):"
echo "  GPG_PRIVATE_KEY  — armored secret key block"
echo "  GPG_KEY_ID       — key id for signing"
echo "  GPG_PASSPHRASE   — optional"
echo ""
echo "Import test (CI uses this pattern):"
echo '  echo "$GPG_PRIVATE_KEY" | gpg --batch --import'
echo '  gpg --list-secret-keys'
echo ""
echo "Signed tag push:"
echo '  git tag -s vX.Y.Z -m "APEX vX.Y.Z"'
echo '  git push origin vX.Y.Z'
echo ""
if [[ -n "${GPG_PRIVATE_KEY:-}" ]]; then
  echo "$GPG_PRIVATE_KEY" | gpg --batch --import
  gpg --list-secret-keys
  echo "GPG key imported from GPG_PRIVATE_KEY env."
else
  echo "Set GPG_PRIVATE_KEY to import automatically, or run gpg --import manually."
fi
