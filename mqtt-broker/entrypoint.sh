#!/bin/sh
# =========================================================================
# SM-Park - Entrypoint du broker Mosquitto
# -------------------------------------------------------------------------
# Génère le fichier de mots de passe (/mosquitto/data/passwd) à partir des
# variables d'environnement MQTT_USERNAME / MQTT_PASSWORD, puis lance le
# broker avec la configuration fournie.
# =========================================================================
set -e

PASSWD_FILE="/mosquitto/data/passwd"
CONF_FILE="/mosquitto/config/mosquitto.conf"

mkdir -p /mosquitto/data /mosquitto/log

if [ -z "${MQTT_USERNAME}" ] || [ -z "${MQTT_PASSWORD}" ]; then
    echo "[SM-Park][MQTT] ERREUR: MQTT_USERNAME et MQTT_PASSWORD sont requis." >&2
    exit 1
fi

echo "[SM-Park][MQTT] Génération du fichier de mots de passe..."
rm -f "${PASSWD_FILE}"
touch "${PASSWD_FILE}"
mosquitto_passwd -b "${PASSWD_FILE}" "${MQTT_USERNAME}" "${MQTT_PASSWORD}"
chmod 600 "${PASSWD_FILE}"

# Le processus Mosquitto tourne en root dans ce conteneur : le fichier reste
# lisible. On s'assure toutefois de la propriété pour les images récentes.
chown mosquitto:mosquitto "${PASSWD_FILE}" 2>/dev/null || true

echo "[SM-Park][MQTT] Utilisateur '${MQTT_USERNAME}' configuré. Démarrage du broker."

exec /usr/sbin/mosquitto -c "${CONF_FILE}"
