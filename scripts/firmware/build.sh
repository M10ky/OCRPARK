#!/usr/bin/env bash
# =========================================================================
# SM-Park - Compile du firmware ESP32
# -------------------------------------------------------------------------
# Garantit la présence de `secrets.ini` (copie l'exemple s'il manque) puis
# lance `pio run`.
#
# Rappel : PlatformIO ignore SILENCIEUSEMENT un `extra_configs` introuvable.
# Sans ce garde-fou, un `pio run` « réussit » mais produit un firmware qui ne
# se connecte jamais (identifiants de substitution CHANGE_ME_*).
# =========================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FW_DIR="$ROOT/firmware/esp32"
SECRETS="$FW_DIR/secrets.ini"
EXAMPLE="$FW_DIR/secrets.ini.example"

if [ ! -f "$SECRETS" ]; then
  echo "[build] secrets.ini absent -> copie de secrets.ini.example"
  echo "[build] Renseignez Wi-Fi et MQTT dans firmware/esp32/secrets.ini"
  cp "$EXAMPLE" "$SECRETS"
fi

cd "$FW_DIR"
exec pio run "$@"
