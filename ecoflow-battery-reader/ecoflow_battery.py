#!/usr/bin/env python3
"""EcoFlow application MQTT -> target HA MQTT bridge, DELTA 3 Classic.

Cloud publishes are restricted to an empty read-only property/get snapshot.
No property/set, no developer API, no plug control. All secrets stay in memory.
"""
import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import signal
import ssl
import stat
import threading
import time
from urllib import error, parse, request

import paho.mqtt.client as mqtt
from google.protobuf import descriptor_pool, message_factory
from google.protobuf.json_format import MessageToDict

LOG = logging.getLogger('ecoflow_mqtt')
DESCRIPTOR_SHA256 = 'c34e0f429a358dcafb94be7293fbd8d200f6700fbc929d7557affc7a2d83634a'
API_HOSTS = {'https://api-e.ecoflow.com', 'https://api-a.ecoflow.com', 'https://api.ecoflow.com'}
BMS_COMMANDS = {(3, 1), (3, 2), (3, 30), (3, 50), (32, 1), (32, 3), (32, 50),
                (32, 51), (32, 52), (254, 24), (254, 25), (254, 26), (254, 27),
                (254, 28), (254, 29), (254, 30)}


class SafeError(Exception):
    """Only predefined, nonsecret error codes may be logged."""


class AuthRejected(SafeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SafeError('redirect_refused')


def load_config(path, observe=False):
    p = Path(path)
    try:
        mode = p.stat().st_mode
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise SafeError('config_permissions')
        cfg = json.loads(p.read_text())
    except (OSError, ValueError):
        raise SafeError('config_unreadable') from None
    if not isinstance(cfg, dict):
        raise SafeError('config_invalid')
    cfg.setdefault('api_host', 'https://api-e.ecoflow.com')
    cfg.setdefault('instance_id', 'ecoflow-bridge-site-batterie')
    cfg.setdefault('snapshot_interval', 60)
    cfg.setdefault('freshness_seconds', 180)
    cfg.setdefault('topic_prefix', 'ecoflow/delta3classic')
    for field in ('email', 'password', 'device_sn', 'instance_id'):
        if not isinstance(cfg.get(field), str) or not cfg[field]:
            raise SafeError('config_invalid')
    if cfg['api_host'] not in API_HOSTS or not re.fullmatch(r'[A-Za-z0-9]+', cfg['device_sn']):
        raise SafeError('config_invalid')
    if not isinstance(cfg['snapshot_interval'], int) or not 60 <= cfg['snapshot_interval'] <= 3600:
        raise SafeError('config_invalid')
    if cfg['freshness_seconds'] != 180:
        # HA's YAML and automation use the same bound. Change all together.
        raise SafeError('freshness_must_be_180')
    prefix = cfg['topic_prefix']
    if not isinstance(prefix, str) or not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', prefix):
        raise SafeError('config_invalid')
    if not observe:
        local = cfg.get('local_mqtt')
        if not isinstance(local, dict):
            raise SafeError('local_mqtt_missing')
        for field in ('host', 'username', 'password'):
            if not isinstance(local.get(field), str) or not local[field]:
                raise SafeError('local_mqtt_invalid')
        local.setdefault('port', 1883)
        local.setdefault('tls', False)
        if isinstance(local['port'], bool) or not isinstance(local['port'], int) or not 1 <= local['port'] <= 65535:
            raise SafeError('local_mqtt_invalid')
        if not isinstance(local['tls'], bool):
            raise SafeError('local_mqtt_invalid')
    return cfg


def http_json(opener, url, method='GET', data=None, headers=None, auth=False):
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with opener.open(req, timeout=12) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if response.status != 200 or len(raw) > 2 * 1024 * 1024:
                raise SafeError('http_failure')
        payload = json.loads(raw)
    except SafeError:
        raise
    except (error.URLError, OSError, ValueError):
        raise SafeError('http_or_json_failure') from None
    if not isinstance(payload, dict) or str(payload.get('code')) != '0':
        cls = AuthRejected if auth else SafeError
        raise cls('application_auth_rejected' if auth else 'application_api_rejected')
    if not isinstance(payload.get('data'), dict):
        raise SafeError('application_payload_invalid')
    return payload['data']


def login(cfg):
    opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    body = json.dumps({'email': cfg['email'], 'password': base64.b64encode(cfg['password'].encode()).decode(),
                       'scene': 'IOT_APP', 'userType': 'ECOFLOW'}).encode()
    response = http_json(opener, cfg['api_host'] + '/auth/login', 'POST', body,
                         {'lang': 'en_US', 'content-type': 'application/json'}, auth=True)
    try:
        token = response['token']
        uid = response['user']['userId']
        if not isinstance(token, str) or not token:
            raise KeyError('token')
    except (KeyError, TypeError):
        raise SafeError('login_payload_invalid') from None
    cert = http_json(opener, cfg['api_host'] + '/iot-auth/app/certification',
                     data=parse.urlencode({'userId': uid}).encode(),
                     headers={'lang': 'en_US', 'authorization': 'Bearer ' + token, 'content-type': 'application/json'})
    try:
        broker, port = cert['url'], int(cert['port'])
        account, password = cert['certificateAccount'], cert['certificatePassword']
    except (KeyError, TypeError, ValueError):
        raise SafeError('certificate_invalid') from None
    if not isinstance(broker, str) or not re.fullmatch(r'[A-Za-z0-9.-]+\.ecoflow\.com', broker) or port != 8883:
        raise SafeError('unexpected_broker')
    if not isinstance(account, str) or not account or not isinstance(password, str) or not password:
        raise SafeError('certificate_invalid')
    suffix = hashlib.sha256(cfg['instance_id'].encode()).hexdigest()[:32].upper()
    return {'host': broker, 'port': port, 'username': account, 'password': password,
            'uid': str(uid), 'client_id': 'ANDROID_' + suffix + '_' + str(uid)}


@dataclass(frozen=True)
class Metric:
    value: float | int | str
    received_at: float
    source: str


# Model-specific field paths. No generic search for words containing "soc".
FIELDS = {
    'soc': ('cms_batt_soc', 'msg32_2_1.cms_batt_soc'),
    'charge_limit': ('cms_max_chg_soc', 'msg32_2_1.cms_max_chg_soc'),
    'discharge_limit': ('cms_min_dsg_soc', 'msg32_2_1.cms_min_dsg_soc'),
    'charge_state_code': ('cms_chg_dsg_state', 'msg32_2_1.cms_chg_dsg_state'),
    'power_in': ('pow_in_sum_w',),
    'power_out': ('pow_out_sum_w',),
    'power_ac_in': ('pow_get_ac_in',),
    'power_pv': ('pow_get_pv',),
}


def lookup(data, path):
    for part in path.split('.'):
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not low <= value <= high:
        return None
    return int(value) if float(value).is_integer() else value


def extract(data, source, received_at):
    output = {}
    for metric, paths in FIELDS.items():
        for path in paths:
            value = lookup(data, path)
            if value is None:
                continue
            if metric in ('soc', 'charge_limit', 'discharge_limit'):
                value = number(value, 0 if metric != 'charge_limit' else 1, 100)
            elif metric == 'charge_state_code':
                value = number(value, -32768, 32767)
                if value is not None and not float(value).is_integer():
                    value = None
            else:
                value = number(value, 0, 100000)
            if value is not None:
                output[metric] = Metric(value, received_at, source + ':' + path)
                if metric == 'charge_state_code':
                    label = {0: 'idle', 1: 'discharging', 2: 'charging'}.get(value, 'unknown')
                    output['charge_state'] = Metric(label, received_at, source + ':' + path)
            break
    return output


class Decoder:
    def __init__(self, path=None):
        raw = (Path(path) if path else Path(__file__).with_name('delta3_descriptor.bin')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != DESCRIPTOR_SHA256:
            raise SafeError('descriptor_hash_mismatch')
        desc = descriptor_pool.DescriptorPool().AddSerializedFile(raw)
        self.proto = {name: message_factory.GetMessageClass(item) for name, item in desc.message_types_by_name.items()}

    def decode(self, raw, received_at):
        if len(raw) > 256 * 1024:
            raise SafeError('telemetry_too_large')
        try:
            raw = base64.b64decode(raw, validate=True)
        except (ValueError, base64.binascii.Error):
            pass
        packet = self.proto['Delta3HeaderMessage']()
        packet.ParseFromString(raw)
        output = {}
        for header in packet.header:
            pair = (header.cmd_func, header.cmd_id)
            name = {(254, 21): 'Delta3DisplayPropertyUpload',
                    (254, 22): 'Delta3RuntimePropertyUpload',
                    (32, 2): 'Delta3CMSHeartBeatReport'}.get(pair)
            if pair in BMS_COMMANDS:
                # BMS "soc" is not silently substituted for combined CMS SOC.
                name = 'Delta3BMSHeartBeatReport'
            if not name or not header.pdata:
                continue
            pdata = header.pdata
            if header.enc_type == 1 and header.src != 32:
                pdata = bytes((value ^ header.seq) & 0xff for value in pdata)
            elif header.enc_type not in (0, 1):
                continue
            report = self.proto[name]()
            report.ParseFromString(pdata)
            data = MessageToDict(report, preserving_proto_field_name=True)
            output.update(extract(data, name, received_at))
        return output

    def snapshot_request(self):
        # Mirrors the app's empty "get all" envelope. No set command/pdata.
        packet = self.proto['Delta3SendHeaderMsg']()
        header = packet.msg.add()
        header.src = 32
        header.dest = 32
        header.seq = int(time.time() * 1000) % 2147483647
        setattr(header, 'from', 'EcoFlowSocReadOnly')
        return packet.SerializeToString()


def fresh(metric, now, seconds=180):
    return metric is not None and 0 <= now - metric.received_at < seconds


class ReadOnlyCloudClient(mqtt.Client):
    def __init__(self, get_topic, **kwargs):
        super().__init__(**kwargs)
        self.allowed_get_topic = get_topic

    def publish(self, topic, payload=None, qos=0, retain=False, properties=None):
        if topic != self.allowed_get_topic or retain:
            raise SafeError('cloud_publish_forbidden')
        return super().publish(topic, payload, qos, retain, properties)


class Bridge:
    def __init__(self, cfg, observe=False, snapshots=True):
        self.cfg, self.observe, self.snapshots = cfg, observe, snapshots
        self.decoder = Decoder()
        self.stop = threading.Event()
        self.session_end = threading.Event()
        self.cloud_ready = threading.Event()
        self.cloud_subscribed = threading.Event()
        self.local_ready = threading.Event()
        self.lock = threading.RLock()
        self.metrics = {}
        self.messages = self.read_queries = self.decode_errors = 0
        self.local = self.cloud = None
        self.cloud_auth_rejected = False

    def local_publish(self, suffix, payload, retain=False):
        if self.local and self.local_ready.is_set():
            return self.local.publish(self.cfg['topic_prefix'] + '/' + suffix, payload, qos=1, retain=retain)
        return None

    def availability(self):
        self.local_publish('availability', 'online' if self.cloud_subscribed.is_set() else 'offline', True)

    def publish_metrics(self, metrics):
        if self.observe:
            for key in ('soc', 'charge_limit'):
                if key in metrics:
                    LOG.info('observation metric=%s value=%s', key, metrics[key].value)
            return
        for key, metric in metrics.items():
            if fresh(metric, time.time()):
                payload = json.dumps({'value': metric.value, 'received_at': metric.received_at,
                                      'source': metric.source}, allow_nan=False, separators=(',', ':'))
                self.local_publish(key, payload, retain=False)

    def start_local(self):
        if self.observe:
            return
        cfg = self.cfg['local_mqtt']
        client_id = 'ecoflow-bridge-' + hashlib.sha256(self.cfg['instance_id'].encode()).hexdigest()[:16]
        self.local = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=True)
        self.local.username_pw_set(cfg['username'], cfg['password'])
        if cfg['tls']:
            self.local.tls_set_context(ssl.create_default_context(cafile=cfg.get('ca_file')))
        self.local.will_set(self.cfg['topic_prefix'] + '/availability', 'offline', qos=1, retain=True)
        self.local.reconnect_delay_set(min_delay=5, max_delay=120)
        self.local.connect_timeout = 12

        def connected(client, userdata, flags, reason, properties):
            if reason.is_failure:
                LOG.warning('target_mqtt_connection_rejected')
                return
            self.local_ready.set()
            self.availability()
            with self.lock:
                self.publish_metrics(dict(self.metrics))
            LOG.info('target_mqtt_connected')

        def disconnected(client, userdata, flags, reason, properties):
            self.local_ready.clear()
            LOG.warning('target_mqtt_disconnected')

        self.local.on_connect, self.local.on_disconnect = connected, disconnected
        self.local.connect_async(cfg['host'], cfg['port'], keepalive=30)
        self.local.loop_start()

    def on_message(self, client, userdata, message):
        if message.retain:
            # Receiving a retained old frame must not refresh measurement age.
            return
        try:
            values = self.decoder.decode(message.payload, time.time())
        except Exception:
            self.decode_errors += 1
            return
        self.messages += 1
        with self.lock:
            self.metrics.update(values)
            self.publish_metrics(values)

    def cloud_session(self, credentials, duration_deadline):
        self.session_end.clear()
        self.cloud_ready.clear()
        self.cloud_subscribed.clear()
        self.cloud_auth_rejected = False
        with self.lock:
            self.metrics.clear()  # Never republish cache from a previous session.
        uid, serial = credentials['uid'], self.cfg['device_sn']
        get_topic = '/app/' + uid + '/' + serial + '/thing/property/get'
        topics = [('/app/device/property/' + serial, 1), (get_topic + '_reply', 1)]
        self.cloud = ReadOnlyCloudClient(get_topic, callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                        client_id=credentials['client_id'], clean_session=True,
                                        protocol=mqtt.MQTTv311, reconnect_on_failure=False)
        self.cloud.username_pw_set(credentials['username'], credentials['password'])
        self.cloud.tls_set_context(ssl.create_default_context())
        self.cloud.connect_timeout = 12

        def connected(client, userdata, flags, reason, properties):
            if reason.is_failure:
                self.cloud_auth_rejected = True
                self.session_end.set()
                return
            self.cloud_ready.set()
            client.subscribe(topics)
            LOG.info('application_mqtt_connected')

        def subscribed(client, userdata, mid, reasons, properties):
            if not reasons or any(reason.is_failure for reason in reasons):
                self.session_end.set()
                return
            self.cloud_subscribed.set()
            self.availability()
            LOG.info('application_mqtt_subscribed')

        def disconnected(client, userdata, flags, reason, properties):
            self.cloud_ready.clear()
            self.cloud_subscribed.clear()
            self.availability()
            self.session_end.set()

        self.cloud.on_connect, self.cloud.on_subscribe = connected, subscribed
        self.cloud.on_disconnect, self.cloud.on_message = disconnected, self.on_message
        next_snapshot, next_heartbeat = 0.0, 0.0
        try:
            self.cloud.connect(credentials['host'], credentials['port'], keepalive=30)
            self.cloud.loop_start()
            connection_deadline = time.monotonic() + 20
            while not self.stop.is_set() and not self.session_end.is_set():
                now = time.monotonic()
                if duration_deadline and now >= duration_deadline:
                    self.stop.set()
                    break
                if not self.cloud_subscribed.is_set() and now > connection_deadline:
                    raise SafeError('mqtt_subscription_timeout')
                if self.cloud_subscribed.is_set() and self.snapshots and now >= next_snapshot:
                    info = self.cloud.publish(get_topic, self.decoder.snapshot_request(), qos=1, retain=False)
                    if info.rc == mqtt.MQTT_ERR_SUCCESS:
                        self.read_queries += 1
                        LOG.info('read_snapshot_requested count=%s', self.read_queries)
                    next_snapshot = now + self.cfg['snapshot_interval']
                if now >= next_heartbeat:
                    with self.lock:
                        soc_fresh = fresh(self.metrics.get('soc'), time.time())
                    LOG.info('heartbeat cloud=%s target=%s soc_fresh=%s messages=%s read_queries=%s decode_errors=%s',
                             self.cloud_subscribed.is_set(), self.local_ready.is_set(), soc_fresh,
                             self.messages, self.read_queries, self.decode_errors)
                    next_heartbeat = now + 60
                self.stop.wait(0.5)
        finally:
            self.cloud_subscribed.clear()
            self.availability()
            self.cloud.disconnect()
            self.cloud.loop_stop()
        if self.cloud_auth_rejected:
            raise AuthRejected('application_mqtt_auth_rejected')

    def run(self, duration=None):
        deadline = time.monotonic() + duration if duration else None
        self.start_local()
        backoff = 30
        try:
            while not self.stop.is_set():
                if deadline and time.monotonic() >= deadline:
                    break
                try:
                    credentials = login(self.cfg)
                    LOG.info('application_login_and_certificate_ok')
                    self.cloud_session(credentials, deadline)
                    delay = backoff
                except AuthRejected as exc:
                    LOG.error('%s retry_seconds=900', str(exc))
                    delay = 900
                except Exception as exc:
                    # Do not log exception content, HTTP bodies, tokens or passwords.
                    LOG.warning('session_failed type=%s retry_seconds=%s', type(exc).__name__, backoff)
                    delay = backoff
                self.cloud_subscribed.clear()
                self.availability()
                if deadline:
                    delay = min(delay, max(0, deadline - time.monotonic()))
                self.stop.wait(delay)
                backoff = min(backoff * 2, 300)
        finally:
            self.cloud_subscribed.clear()
            if self.local:
                info = self.local_publish('availability', 'offline', True)
                if info:
                    try:
                        info.wait_for_publish(timeout=3)
                    except Exception:
                        pass
                self.local.disconnect()
                self.local.loop_stop()
            LOG.info('collector_stopped messages=%s read_queries=%s decode_errors=%s',
                     self.messages, self.read_queries, self.decode_errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--observe', action='store_true', help='Do not connect/publish to a target HA MQTT broker')
    parser.add_argument('--duration', type=int, help='Bounded diagnostic run in seconds (minimum 30)')
    parser.add_argument('--passive', action='store_true', help='Subscribe only; never request snapshots')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.duration is not None and args.duration < 30:
        parser.error('--duration must be at least 30')
    try:
        cfg = load_config(args.config, args.observe)
        bridge = Bridge(cfg, observe=args.observe, snapshots=not args.passive)
        signal.signal(signal.SIGTERM, lambda *unused: bridge.stop.set())
        signal.signal(signal.SIGINT, lambda *unused: bridge.stop.set())
        bridge.run(args.duration)
    except Exception as exc:
        code = str(exc) if isinstance(exc, SafeError) else type(exc).__name__
        LOG.error('collector_failed code=%s', code)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
