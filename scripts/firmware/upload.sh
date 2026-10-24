#!/usr/bin/env bash
# =========================================================================
# SM-Park - Upload du firmware sur l'ESP32 (via WSL -> USB)
# =========================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FW_DIR="$ROOT/firmware/esp32"

cd "$FW_DIR"
exec pio run --target upload "$@"
