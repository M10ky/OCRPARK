1. Exposer l'USB à WSL2 (sinon pio ne voit pas la carte). PowerShell admin Windows :
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
Puis dans WSL : ls /dev/ttyUSB* /dev/ttyACM*. (Alternative : flasher depuis Windows avec PlatformIO.)
2. Compiler + uploader
pio run -d firmware/esp32 -t upload          # ajouter --upload-port /dev/ttyUSB0 si besoin
pio device monitor -d firmware/esp32 --baud 115200
3. Vérifier le boot série — attendu :
- connexion Wi-Fi OK
- initialized puis idle
- heartbeat toutes les 5 s
4. Vérifier côté broker que l'ESP32 s'est connecté :
docker compose logs --tail=20 mqtt-broker   # doit montrer client "smpark-esp32"
5. Test MQTT de bout en bout (l'ESP32 joue le rôle du « device ») :
# T1
docker compose exec mqtt-broker mosquitto_sub -h localhost -u smpark -P change_me_mqtt -t barrier/state -v
# T2
docker compose exec mqtt-broker mosquitto_pub -h localhost -u smpark -P change_me_mqtt -t parking/barrier/command -m '{"action":"open"}'
Attendu T1 : opening, open, closing, closed.
6. Test d'intégration complet (le vrai flux) :
- ajout d'une plaque autorisée, puis POST /api/orchestrate/upload (voir docs/tests/phase-5-tests-backend.md)
- le backend publie parking/barrier/command → l'ESP32 ouvre → barrier/state remonte.
7. Si l'ESP32 ne se connecte pas au broker : autoriser le port 1883 dans le pare-feu Windows (PowerShell admin) — voir Partie C.3 de la doc. Vérifie aussi que l'ESP32 et l'hôte sont bien sur le même sous-réseau (192.168.1.0/24).
Ce qui restera après (Phase 8, hors « connexion ESP32 »)
- Le backend reçoit barrier/state mais ne fait que le logger (backend/app/services/mqtt.py:61-66) : il faut le relayer au WebSocket et éventuellement le persister pour que le frontend affiche l'état de la barrière.
- Affichage temps réel dans le frontend (ws://localhost:8000/ws/events).
- Tests d'intégration complets (Phase 8) + finalisation doc (Phase 9).
Dis-moi quand la carte est branchée et je t'accompagne pour l'upload/monitor et le test MQTT réel.