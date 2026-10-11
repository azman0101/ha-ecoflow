#!/usr/bin/env python3
"""Turn the Home Assistant add-on options (/data/options.json) into the collector's config file.

When ``local_mqtt.host`` is empty, the MQTT broker is taken from the Supervisor's ``mqtt`` service
(declared as ``services: [mqtt:want]`` in config.yaml), so users do not have to type broker credentials.
No secret is ever printed.
"""
import json
import os
from pathlib import Path
import sys
from urllib import error, request

OPTIONS = Path('/data/options.json')
TARGET = Path('/tmp/ecoflow.json')  # nosec B108 - container-private; created exclusively with mode 600 below
SERVICE_URL = 'http://supervisor/services/mqtt'  # Fixed internal URL of the Supervisor API.

DEFAULTS = {'api_host': 'https://api-e.ecoflow.com', 'instance_id': 'ecoflow-bridge', 'snapshot_interval': 60,
            'freshness_seconds': 180, 'topic_prefix': 'ecoflow/delta3classic', 'discovery': True,
            'discovery_prefix': 'homeassistant', 'target_margin': 0.2}


class PrepareError(Exception):
    """Message is a fixed, nonsecret code or sentence."""


def supervisor_mqtt():
    token = os.environ.get('SUPERVISOR_TOKEN')
    if not token:
        raise PrepareError('SUPERVISOR_TOKEN is not set')
    req = request.Request(SERVICE_URL, headers={'Authorization': 'Bearer ' + token})
    try:
        with request.urlopen(req, timeout=10) as response:  # nosec B310 - constant http://supervisor URL
            payload = json.loads(response.read(65536))
    except (error.URLError, OSError, ValueError):
        raise PrepareError('the Supervisor MQTT service is unavailable') from None
    data = payload.get('data') if isinstance(payload, dict) and payload.get('result') == 'ok' else None
    if not isinstance(data, dict) or not data.get('host') or not data.get('username') or not data.get('password'):
        raise PrepareError('no MQTT broker is provided by the Supervisor')
    return {'host': data['host'], 'port': int(data.get('port', 1883)), 'username': data['username'],
            'password': data['password'], 'tls': bool(data.get('ssl', False))}


def build_config(options, fetch_service=None):
    cfg = {**DEFAULTS, **{k: v for k, v in options.items() if v not in (None, '')}}
    local = {k: v for k, v in (cfg.get('local_mqtt') or {}).items() if v not in (None, '')}
    if not local.get('host'):
        try:
            local = (fetch_service or supervisor_mqtt)()
        except PrepareError as exc:
            raise PrepareError('local_mqtt.host is empty and %s. Install the Mosquitto broker add-on or fill '
                               'in local_mqtt manually.' % exc) from None
        print('[INFO] MQTT broker provided by the Supervisor (host %s)' % local['host'])
    local.setdefault('port', 1883)
    local.setdefault('tls', False)
    cfg['local_mqtt'] = local
    return cfg


def main():
    if not OPTIONS.exists():
        print('[ERROR] /data/options.json not found', file=sys.stderr)
        return 1
    try:
        cfg = build_config(json.loads(OPTIONS.read_text(encoding='utf-8')))
    except PrepareError as exc:
        print('[ERROR] %s' % exc, file=sys.stderr)
        return 1
    # Create the file already restricted and never follow a pre-planted link: the collector refuses
    # configs readable by others.
    TARGET.unlink(missing_ok=True)
    fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(cfg, stream, indent=2)
    print('[INFO] Configuration written to %s (mode 600)' % TARGET)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
