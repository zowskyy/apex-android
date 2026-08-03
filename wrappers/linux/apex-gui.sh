#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"
apex_python gui "$@"
