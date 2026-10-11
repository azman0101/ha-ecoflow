#!/bin/sh
set -e

echo "[INFO] Démarrage du collecteur EcoFlow DELTA 3..."
python3 -B /app/prepare_config.py
exec python3 -B /app/ecoflow_battery.py --config /tmp/ecoflow.json
