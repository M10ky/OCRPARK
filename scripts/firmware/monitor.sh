#!/usr/bin/env bash
# =========================================================================
# SM-Park - Moniteur série de l'ESP32 (logs Wi-Fi / MQTT / barrière)
# =========================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FW_DIR="$ROOT/firmware/esp32"

cd "$FW_DIR"
exec pio device monitor "$@"
