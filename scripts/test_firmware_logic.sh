#!/usr/bin/env bash
# =========================================================================
# SM-Park - Tests natifs du firmware (machine hôte, sans ESP32)
# -------------------------------------------------------------------------
# Compile `src/barrier.cpp` + `src/command.cpp` avec un mock d'Arduino
# (`test/mocks/Arduino.h`) et exécute les tests unitaires :
#   - validation stricte des commandes (aucun servo, aucun ACK sur erreur)
#   - séquence d'états d'une barrière
#   - indépendance entry / exit
#
# Utilisation :
#   scripts/test_firmware_logic.sh
#
# Portée : test du CONTRAT (logique pure). Les entrées/sorties matérielles
# réelles (HC-SR04, IR, servo) ne sont pas couvertes ici : elles exigent un
# ESP32 sur le bureau.
# =========================================================================
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FW="$ROOT/firmware/esp32"
OUT="$FW/.pio/native-test"
CXX="${CXX:-g++}"

mkdir -p "$OUT"

echo "[compile] tests natifs du firmware"
"$CXX" -std=c++17 -Wall -Wextra -Wno-unused-parameter \
  -I "$FW/test/mocks" \
  -I "$FW/src" \
  "$FW/src/command.cpp" \
  "$FW/src/barrier.cpp" \
  "$FW/test/native/test_firmware.cpp" \
  -o "$OUT/test_firmware"

echo "[run] $OUT/test_firmware"
"$OUT/test_firmware"
