#!/bin/sh
set -e

echo "[INFO] Démarrage du collecteur EcoFlow DELTA 3..."

python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

opts_path = Path('/data/options.json')
if not opts_path.exists():
    print("[ERROR] Fichier /data/options.json introuvable", file=sys.stderr)
    sys.exit(1)

cfg = json.loads(opts_path.read_text(encoding='utf-8'))

cfg.setdefault('api_host', 'https://api-e.ecoflow.com')
cfg.setdefault('instance_id', 'ecoflow-bridge')
cfg.setdefault('snapshot_interval', 60)
cfg.setdefault('freshness_seconds', 180)
cfg.setdefault('topic_prefix', 'ecoflow/delta3classic')

if 'local_mqtt' in cfg and isinstance(cfg['local_mqtt'], dict):
    cfg['local_mqtt'].setdefault('host', 'core-mosquitto')
    cfg['local_mqtt'].setdefault('port', 1883)
    cfg['local_mqtt'].setdefault('tls', False)

target = Path('/tmp/ecoflow.json')
target.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
target.chmod(0o600)
print("[INFO] Configuration préparée avec succès dans /tmp/ecoflow.json (mode 600)")
PY

exec python3 -B /app/ecoflow_battery.py --config /tmp/ecoflow.json
