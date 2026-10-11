"""Offline tests: synthetic protobuf, fake MQTT clients, discovery payloads, add-on options, blueprint."""
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import yaml

import ecoflow_battery as reader
import ecoflow_discovery as discovery
import prepare_config as prepare

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

CFG = {'api_host': 'https://api-e.ecoflow.com', 'email': 'test@example.invalid', 'password': 'TESTPASSWORD',
       'device_sn': 'TESTSN', 'instance_id': 'test-instance', 'snapshot_interval': 60,
       'freshness_seconds': 180, 'topic_prefix': 'ecoflow/delta3classic', 'discovery': True,
       'discovery_prefix': 'homeassistant', 'target_margin': 0.2,
       'local_mqtt': {'host': 'test.invalid', 'port': 1883, 'username': 'test', 'password': 'test', 'tls': False}}


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.decoder = reader.Decoder()

    def packet(self, message, cmd_func=32, cmd_id=2, xor=False, src=7):
        packet = self.decoder.proto['Delta3HeaderMessage']()
        header = packet.header.add()
        header.cmd_func, header.cmd_id, header.src = cmd_func, cmd_id, src
        pdata = message.SerializeToString()
        if xor:
            header.enc_type = 1
            header.seq = 13
            pdata = bytes(b ^ 13 for b in pdata)
        header.pdata = pdata
        return packet.SerializeToString()

    def test_classic_cms_paths_and_zero(self):
        for soc in (0, 89.04, 100):
            report = self.decoder.proto['Delta3CMSHeartBeatReport']()
            report.msg32_2_1.cms_batt_soc = soc
            report.msg32_2_1.cms_max_chg_soc = 90
            report.msg32_2_1.cms_min_dsg_soc = 1
            values = self.decoder.decode(self.packet(report), 500)
            self.assertAlmostEqual(values['soc'].value, soc, places=3)
            self.assertEqual(values['soc'].received_at, 500)
            self.assertEqual(values['charge_limit'].value, 90)
            self.assertEqual(values['discharge_limit'].value, 1)
            self.assertIn('msg32_2_1.cms_batt_soc', values['soc'].source)

    def test_regular_delta3_display_soc_supported(self):
        report = self.decoder.proto['Delta3DisplayPropertyUpload']()
        report.cms_batt_soc = 40
        report.pow_in_sum_w = 0
        values = self.decoder.decode(self.packet(report, 254, 21), 500)
        self.assertEqual(values['soc'].value, 40)
        self.assertEqual(values['power_in'].value, 0)

    def test_unknown_charge_state_does_not_become_charging(self):
        report = self.decoder.proto['Delta3CMSHeartBeatReport']()
        report.msg32_2_1.cms_chg_dsg_state = -1
        values = self.decoder.decode(self.packet(report), 500)
        self.assertEqual(values['charge_state_code'].value, -1)
        self.assertEqual(values['charge_state'].value, 'unknown')

    def test_known_charge_states(self):
        for code, expected in [(0, 'idle'), (1, 'discharging'), (2, 'charging')]:
            values = reader.extract({'cms_chg_dsg_state': code}, 'test', 500)
            self.assertEqual(values['charge_state'].value, expected)

    def test_xor_and_base64(self):
        import base64
        report = self.decoder.proto['Delta3CMSHeartBeatReport']()
        report.msg32_2_1.cms_batt_soc = 30
        raw = self.packet(report, xor=True)
        self.assertEqual(self.decoder.decode(raw, 500)['soc'].value, 30)
        self.assertEqual(self.decoder.decode(base64.b64encode(raw), 500)['soc'].value, 30)

    def test_partial_power_report_does_not_refresh_soc(self):
        report = self.decoder.proto['Delta3DisplayPropertyUpload']()
        report.pow_in_sum_w = 100
        values = self.decoder.decode(self.packet(report, 254, 21), 800)
        self.assertNotIn('soc', values)
        cache = {'soc': reader.Metric(100, 500, 'old')}
        cache.update(values)
        self.assertFalse(reader.fresh(cache['soc'], 800))
        self.assertTrue(reader.fresh(cache['power_in'], 800))

    def test_bms_soc_is_not_substituted_for_global_soc(self):
        report = self.decoder.proto['Delta3BMSHeartBeatReport']()
        report.soc = 100
        report.f32_show_soc = 100
        self.assertNotIn('soc', self.decoder.decode(self.packet(report, 32, 50), 500))

    def test_bad_values_are_rejected(self):
        for value in (True, -1, 101, float('nan'), float('inf'), '100', None):
            self.assertNotIn('soc', reader.extract({'cms_batt_soc': value}, 'test', 500))
        self.assertNotIn('charge_limit', reader.extract({'cms_max_chg_soc': 0}, 'test', 500))

    def test_false_zero_is_never_manufactured(self):
        values = reader.extract({'pow_in_sum_w': 0}, 'test', 500)
        self.assertEqual(set(values), {'power_in'})
        self.assertEqual(values['power_in'].value, 0)

    def test_expiry_boundary_and_clock_skew(self):
        metric = reader.Metric(100, 500, 'test')
        self.assertTrue(reader.fresh(metric, 679.9))
        self.assertFalse(reader.fresh(metric, 680))
        self.assertFalse(reader.fresh(metric, 499))
        self.assertFalse(reader.fresh(None, 500))

    def test_snapshot_is_an_empty_read_envelope(self):
        message = self.decoder.proto['Delta3SendHeaderMsg']()
        message.ParseFromString(self.decoder.snapshot_request())
        self.assertEqual(len(message.msg), 1)
        header = message.msg[0]
        self.assertEqual((header.src, header.dest), (32, 32))
        self.assertEqual(header.cmd_func, 0)
        self.assertEqual(header.cmd_id, 0)
        self.assertEqual(header.pdata, b'')

    def test_descriptor_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'descriptor.bin'
            path.write_bytes(b'wrong')
            with self.assertRaises(reader.SafeError):
                reader.Decoder(path)


class BridgeTests(unittest.TestCase):
    def test_cloud_set_other_topics_and_retained_get_forbidden(self):
        get = '/app/TESTUSER/TESTSN/thing/property/get'
        client = reader.ReadOnlyCloudClient(get, callback_api_version=reader.mqtt.CallbackAPIVersion.VERSION2)
        with mock.patch.object(reader.mqtt.Client, 'publish') as parent:
            for topic, retain in [(get.replace('/get', '/set'), False), ('/other', False), (get, True)]:
                with self.assertRaises(reader.SafeError):
                    client.publish(topic, b'not a command', retain=retain)
            parent.assert_not_called()
            client.publish(get, b'read-only', qos=1)
            parent.assert_called_once()

    def test_local_states_not_retained_and_stale_cache_not_republished(self):
        bridge = reader.Bridge(CFG)
        bridge.local = mock.Mock()
        bridge.local_ready.set()
        values = {'soc': reader.Metric(0, 499, 'new'), 'charge_limit': reader.Metric(90, 100, 'old')}
        with mock.patch.object(reader.time, 'time', return_value=500):
            bridge.publish_metrics(values)
        bridge.local.publish.assert_called_once()
        args, kwargs = bridge.local.publish.call_args
        self.assertEqual(args[0], 'ecoflow/delta3classic/soc')
        self.assertEqual(json.loads(args[1])['value'], 0)
        self.assertEqual(json.loads(args[1])['received_at'], 499)
        self.assertFalse(kwargs['retain'])

    def test_retained_cloud_payload_ignored(self):
        bridge = reader.Bridge(CFG, observe=True)
        bridge.decoder = mock.Mock()
        bridge.on_message(None, None, SimpleNamespace(retain=True, payload=b'old'))
        bridge.decoder.decode.assert_not_called()
        self.assertEqual(bridge.metrics, {})

    def test_observe_never_publishes_to_ha(self):
        bridge = reader.Bridge(CFG, observe=True)
        bridge.local = mock.Mock()
        bridge.local_ready.set()
        bridge.publish_metrics({'soc': reader.Metric(90, 500, 'test')})
        bridge.local.publish.assert_not_called()

    def test_start_local_lwt_and_credentials_are_separate(self):
        bridge = reader.Bridge(CFG)
        with mock.patch.object(reader.mqtt, 'Client') as factory:
            bridge.start_local()
        local = factory.return_value
        local.will_set.assert_called_once_with('ecoflow/delta3classic/availability', 'offline', qos=1, retain=True)
        local.connect_async.assert_called_once_with('test.invalid', 1883, keepalive=30)
        local.loop_start.assert_called_once()

    def test_config_observe_allows_application_file_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credentials.json'
            cfg = {k: v for k, v in CFG.items() if k != 'local_mqtt'}
            path.write_text(json.dumps(cfg))
            path.chmod(0o600)
            self.assertEqual(reader.load_config(path, observe=True)['device_sn'], 'TESTSN')
            with self.assertRaises(reader.SafeError):
                reader.load_config(path)
            path.chmod(0o644)
            with self.assertRaises(reader.SafeError):
                reader.load_config(path, observe=True)

    def test_login_stable_client_id_and_broker_restriction(self):
        answers = [{'token': 'TESTTOKEN', 'user': {'userId': 42}},
                   {'url': 'mqtt-e.ecoflow.com', 'port': 8883, 'certificateAccount': 'TESTUSER', 'certificatePassword': 'TESTCERT'}]
        with mock.patch.object(reader, 'http_json', side_effect=answers):
            first = reader.login(CFG)
        with mock.patch.object(reader, 'http_json', side_effect=answers):
            second = reader.login(CFG)
        self.assertEqual(first['client_id'], second['client_id'])
        with mock.patch.object(reader, 'http_json', side_effect=[answers[0], {**answers[1], 'url': 'untrusted.invalid'}]):
            with self.assertRaises(reader.SafeError):
                reader.login(CFG)


# --- values of the hand-written 1.0.x YAML: entities of an existing installation must keep them ----------------
LEGACY_ENTITIES = {
    'soc': ('ecoflow_classic_mqtt_soc_v1', 'sensor.ecoflow_batterie'),
    'charge_limit': ('ecoflow_classic_mqtt_charge_limit_v1', 'sensor.ecoflow_plafond_charge'),
    'discharge_limit': ('ecoflow_classic_mqtt_discharge_limit_v1', 'sensor.ecoflow_seuil_decharge'),
    'power_in': ('ecoflow_classic_mqtt_power_in_v1', 'sensor.ecoflow_puissance_entree'),
    'power_out': ('ecoflow_classic_mqtt_power_out_v1', 'sensor.ecoflow_puissance_sortie'),
    'power_ac_in': ('ecoflow_classic_mqtt_power_ac_in_v1', 'sensor.ecoflow_puissance_secteur'),
    'power_pv': ('ecoflow_classic_mqtt_power_pv_v1', 'sensor.ecoflow_puissance_solaire'),
    'charge_state_code': ('ecoflow_classic_mqtt_charge_state_code_v1', 'sensor.ecoflow_etat_charge_brut'),
    'charge_state': ('ecoflow_classic_mqtt_charge_state_v1', 'sensor.ecoflow_etat_charge'),
    'telemetry_fresh': ('ecoflow_classic_telemetry_fresh_v1', 'binary_sensor.ecoflow_telemetrie_recente'),
    'charge_target_reached': ('ecoflow_classic_charge_target_reached_v1',
                              'binary_sensor.ecoflow_charge_cible_atteinte'),
    'collector_connected': ('ecoflow_classic_mqtt_connection_v1', 'binary_sensor.ecoflow_collecteur_connecte'),
}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.payload = discovery.build_payload(CFG, '9.9.9')
        self.components = self.payload['components']

    def test_unique_ids_and_entity_ids_match_the_legacy_yaml(self):
        self.assertEqual({k: (c['unique_id'], c['default_entity_id']) for k, c in self.components.items()},
                         LEGACY_ENTITIES)

    def test_topics(self):
        self.assertEqual(discovery.discovery_topic(CFG), 'homeassistant/device/ecoflow_testsn/config')
        self.assertEqual(discovery.status_topic(CFG), 'homeassistant/status')
        custom = {**CFG, 'discovery_prefix': 'ha/disc'}
        self.assertEqual(discovery.discovery_topic(custom), 'ha/disc/device/ecoflow_testsn/config')

    def test_one_device_with_a_serial_derived_identifier_and_origin(self):
        self.assertEqual(self.payload['device']['identifiers'], ['ecoflow_testsn'])
        self.assertEqual(self.payload['device']['manufacturer'], 'EcoFlow')
        self.assertEqual(self.payload['origin']['sw_version'], '9.9.9')
        self.assertNotIn('serial_number', self.payload['device'])

    def test_payload_is_serialisable_and_every_component_has_a_platform(self):
        json.dumps(self.payload, ensure_ascii=False)
        self.assertEqual({c['platform'] for c in self.components.values()}, {'sensor', 'binary_sensor'})

    def test_measurements_expire_and_follow_collector_availability(self):
        for key, component in self.components.items():
            if key == 'collector_connected':
                self.assertNotIn('availability_topic', component)
                self.assertEqual(component['state_topic'], 'ecoflow/delta3classic/availability')
                continue
            self.assertEqual(component['expire_after'], 180, key)
            self.assertEqual(component['availability_topic'], 'ecoflow/delta3classic/availability', key)
            self.assertEqual(component['state_topic'], 'ecoflow/delta3classic/' + key)

    def test_sensors_expose_received_at_and_binary_sensors_use_plain_payloads(self):
        for key, component in self.components.items():
            if component['platform'] == 'sensor':
                self.assertIn('received_at', component['json_attributes_template'], key)
                self.assertEqual(component['value_template'], '{{ value_json.value }}')
            else:
                self.assertNotIn('value_template', component, key)

    def test_components_cover_exactly_what_the_bridge_publishes(self):
        published = set(reader.FIELDS) | {'charge_state', 'telemetry_fresh', 'charge_target_reached'}
        self.assertEqual(set(discovery.ENTITIES), published)
        self.assertEqual(set(self.components), published | {'collector_connected'})

    def test_no_real_device_serial_anywhere_in_the_repository(self):
        # Real DELTA 3 serials look like P321 + 12 characters; none may be committed.
        pattern = re.compile(r'P321(?!X{12})[A-Z0-9]{12}')  # documentation placeholder P321XXXXXXXXXXXX is fine
        for path in REPO.rglob('*'):
            if '.git' in path.parts or not path.is_file() or path.suffix == '.bin':
                continue
            self.assertIsNone(pattern.search(path.read_text(errors='ignore')), str(path))


class DerivedStateTests(unittest.TestCase):
    NOW = 500

    def bridge(self, soc=None, limit=None, soc_age=2, limit_age=2, subscribed=True, **overrides):
        bridge = reader.Bridge({**CFG, **overrides}, observe=False)
        if soc is not None:
            bridge.metrics['soc'] = reader.Metric(soc, self.NOW - soc_age, 'test')
        if limit is not None:
            bridge.metrics['charge_limit'] = reader.Metric(limit, self.NOW - limit_age, 'test')
        if subscribed:
            bridge.cloud_subscribed.set()
        return bridge

    def states(self, bridge):
        return bridge.derived_states(self.NOW)

    def test_target_is_the_configured_limit_minus_margin_not_100(self):
        self.assertEqual(self.states(self.bridge(89.8, 90))['charge_target_reached'], 'ON')
        self.assertEqual(self.states(self.bridge(89.79, 90))['charge_target_reached'], 'OFF')
        self.assertEqual(self.states(self.bridge(100, 90))['charge_target_reached'], 'ON')

    def test_margin_is_configurable(self):
        self.assertEqual(self.states(self.bridge(89.99, 90, target_margin=0))['charge_target_reached'], 'OFF')
        self.assertEqual(self.states(self.bridge(88, 90, target_margin=2))['charge_target_reached'], 'ON')

    def test_zero_soc_never_means_full(self):
        states = self.states(self.bridge(0, 90))
        self.assertEqual(states['charge_target_reached'], 'OFF')
        self.assertEqual(states['telemetry_fresh'], 'ON')

    def test_stale_or_missing_measurement_withholds_the_target(self):
        for kwargs in ({'soc_age': 180}, {'limit_age': 180}, {'soc_age': -1}):
            states = self.states(self.bridge(100, 90, **kwargs))
            self.assertNotIn('charge_target_reached', states, kwargs)
        self.assertNotIn('charge_target_reached', self.states(self.bridge(100, None)))
        self.assertNotIn('charge_target_reached', self.states(self.bridge(None, 90)))

    def test_telemetry_fresh_requires_fresh_soc_and_cloud_session(self):
        self.assertEqual(self.states(self.bridge(50, 90))['telemetry_fresh'], 'ON')
        self.assertEqual(self.states(self.bridge(50, 90, soc_age=180))['telemetry_fresh'], 'OFF')
        self.assertEqual(self.states(self.bridge(50, 90, subscribed=False))['telemetry_fresh'], 'OFF')
        self.assertEqual(self.states(self.bridge())['telemetry_fresh'], 'OFF')

    def test_a_fresh_limit_alone_does_not_make_telemetry_fresh(self):
        self.assertEqual(self.states(self.bridge(None, 90))['telemetry_fresh'], 'OFF')

    def test_derived_states_are_published_plain_and_not_retained(self):
        bridge = self.bridge(95, 90)
        bridge.local, bridge.local.publish = mock.Mock(), mock.Mock()
        bridge.local_ready.set()
        with mock.patch.object(reader.time, 'time', return_value=self.NOW):
            bridge.publish_derived()
        calls = {c.args[0]: (c.args[1], c.kwargs) for c in bridge.local.publish.call_args_list}
        self.assertEqual(calls['ecoflow/delta3classic/charge_target_reached'][0], 'ON')
        self.assertEqual(calls['ecoflow/delta3classic/telemetry_fresh'][0], 'ON')
        for _, kwargs in calls.values():
            self.assertFalse(kwargs['retain'])

    def test_observe_mode_publishes_no_derived_state(self):
        bridge = reader.Bridge(CFG, observe=True)
        bridge.local = mock.Mock()
        bridge.local_ready.set()
        bridge.publish_derived()
        bridge.local.publish.assert_not_called()


class DiscoveryLifecycleTests(unittest.TestCase):
    TOPIC = 'homeassistant/device/ecoflow_testsn/config'

    def started(self, **overrides):
        bridge = reader.Bridge({**CFG, **overrides})
        with mock.patch.object(reader.mqtt, 'Client') as factory:
            bridge.start_local()
        return bridge, factory.return_value

    def connect(self, bridge, local):
        local.on_connect(local, None, None, SimpleNamespace(is_failure=False), None)

    def discovery_calls(self, local):
        return [c for c in local.publish.call_args_list if c.args[0] == self.TOPIC]

    def test_discovery_is_published_on_connect_without_retain_and_birth_is_subscribed(self):
        bridge, local = self.started()
        self.connect(bridge, local)
        (call,) = self.discovery_calls(local)
        self.assertFalse(call.kwargs['retain'])
        self.assertEqual(call.kwargs['qos'], 1)
        self.assertEqual(json.loads(call.args[1])['device']['identifiers'], ['ecoflow_testsn'])
        local.subscribe.assert_called_once_with('homeassistant/status', qos=1)

    def test_home_assistant_birth_message_republishes_discovery(self):
        bridge, local = self.started()
        self.connect(bridge, local)
        local.publish.reset_mock()
        local.on_message(local, None, SimpleNamespace(topic='homeassistant/status', payload=b'offline'))
        self.assertEqual(self.discovery_calls(local), [])
        local.on_message(local, None, SimpleNamespace(topic='homeassistant/status', payload=b'online'))
        self.assertEqual(len(self.discovery_calls(local)), 1)
        local.on_message(local, None, SimpleNamespace(topic='other/status', payload=b'online'))
        self.assertEqual(len(self.discovery_calls(local)), 1)

    def test_discovery_can_be_disabled(self):
        bridge, local = self.started(discovery=False)
        self.connect(bridge, local)
        self.assertEqual(self.discovery_calls(local), [])
        local.subscribe.assert_not_called()

    def test_custom_discovery_prefix(self):
        bridge, local = self.started(discovery_prefix='ha/disc')
        self.connect(bridge, local)
        topics = [c.args[0] for c in local.publish.call_args_list]
        self.assertIn('ha/disc/device/ecoflow_testsn/config', topics)
        local.subscribe.assert_called_once_with('ha/disc/status', qos=1)

    def test_nothing_is_published_while_the_broker_connection_is_not_ready(self):
        bridge = reader.Bridge(CFG)
        bridge.local = mock.Mock()
        bridge.publish_discovery()
        bridge.local.publish.assert_not_called()


class ConfigOptionTests(unittest.TestCase):
    def load(self, **changes):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            base = {k: v for k, v in CFG.items() if k not in ('discovery', 'discovery_prefix', 'target_margin')}
            path.write_text(json.dumps({**base, **changes}))
            path.chmod(0o600)
            return reader.load_config(path)

    def test_new_options_have_defaults(self):
        cfg = self.load()
        self.assertEqual((cfg['discovery'], cfg['discovery_prefix'], cfg['target_margin']), (True, 'homeassistant', 0.2))

    def test_invalid_values_are_rejected(self):
        for changes in ({'discovery': 'yes'}, {'discovery_prefix': ''}, {'discovery_prefix': 'a b'},
                        {'discovery_prefix': '/x'}, {'target_margin': True}, {'target_margin': -0.1},
                        {'target_margin': 5.1}, {'target_margin': '0.2'}):
            with self.assertRaises(reader.SafeError, msg=str(changes)):
                self.load(**changes)

    def test_margin_bounds_are_accepted(self):
        self.assertEqual(self.load(target_margin=0)['target_margin'], 0)
        self.assertEqual(self.load(target_margin=5)['target_margin'], 5)


class PrepareConfigTests(unittest.TestCase):
    OPTIONS = {'email': 'test@example.invalid', 'password': 'TESTPASSWORD', 'device_sn': 'TESTSN',
               'instance_id': 'ecoflow-bridge', 'snapshot_interval': 60, 'freshness_seconds': 180,
               'topic_prefix': 'ecoflow/delta3classic', 'discovery': True, 'discovery_prefix': 'homeassistant',
               'target_margin': 0.2,
               'local_mqtt': {'host': '', 'port': 1883, 'username': '', 'password': '', 'tls': False}}
    SERVICE = {'host': 'mqtt-service.invalid', 'port': 1883, 'username': 'test', 'password': 'test', 'tls': False}

    def test_empty_host_uses_the_supervisor_mqtt_service(self):
        cfg = prepare.build_config(self.OPTIONS, fetch_service=lambda: dict(self.SERVICE))
        self.assertEqual(cfg['local_mqtt'], self.SERVICE)

    def test_manual_broker_is_kept_and_the_supervisor_is_not_asked(self):
        manual = {'host': 'broker.invalid', 'port': 8883, 'username': 'u', 'password': 'p', 'tls': True}
        fetch = mock.Mock()
        cfg = prepare.build_config({**self.OPTIONS, 'local_mqtt': manual}, fetch_service=fetch)
        fetch.assert_not_called()
        self.assertEqual(cfg['local_mqtt'], manual)

    def test_missing_service_gives_an_actionable_error_without_secrets(self):
        def unavailable():
            raise prepare.PrepareError('no MQTT broker is provided by the Supervisor')
        with self.assertRaises(prepare.PrepareError) as caught:
            prepare.build_config(self.OPTIONS, fetch_service=unavailable)
        message = str(caught.exception)
        self.assertIn('local_mqtt.host is empty', message)
        self.assertNotIn('TESTPASSWORD', message)

    def test_unset_and_empty_options_fall_back_to_defaults(self):
        options = {**self.OPTIONS, 'discovery_prefix': '', 'target_margin': None, 'topic_prefix': None}
        cfg = prepare.build_config(options, fetch_service=lambda: dict(self.SERVICE))
        self.assertEqual((cfg['discovery_prefix'], cfg['target_margin'], cfg['topic_prefix']),
                         ('homeassistant', 0.2, 'ecoflow/delta3classic'))

    def test_supervisor_response_parsing(self):
        def response(body):
            handle = mock.MagicMock()
            handle.__enter__.return_value.read.return_value = json.dumps(body).encode()
            return handle
        ok = {'result': 'ok', 'data': {'host': 'core-mosquitto', 'port': 1883, 'username': 'u', 'password': 'p',
                                       'ssl': False, 'protocol': '3.1.1'}}
        with mock.patch.dict(os.environ, {'SUPERVISOR_TOKEN': 'TESTTOKEN'}):
            with mock.patch.object(prepare.request, 'urlopen', return_value=response(ok)) as opened:
                self.assertEqual(prepare.supervisor_mqtt(),
                                 {'host': 'core-mosquitto', 'port': 1883, 'username': 'u', 'password': 'p',
                                  'tls': False})
            request = opened.call_args.args[0]
            self.assertEqual(request.full_url, 'http://supervisor/services/mqtt')
            self.assertEqual(request.get_header('Authorization'), 'Bearer TESTTOKEN')
            for body in ({'result': 'error'}, {'result': 'ok', 'data': {}}, {'result': 'ok', 'data': {'host': 'h'}}):
                with mock.patch.object(prepare.request, 'urlopen', return_value=response(body)):
                    with self.assertRaises(prepare.PrepareError):
                        prepare.supervisor_mqtt()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(prepare.PrepareError):
                prepare.supervisor_mqtt()

    def test_main_writes_a_private_file_the_collector_accepts(self):
        with tempfile.TemporaryDirectory() as directory:
            options, target = Path(directory) / 'options.json', Path(directory) / 'ecoflow.json'
            options.write_text(json.dumps(self.OPTIONS))
            with mock.patch.object(prepare, 'OPTIONS', options), mock.patch.object(prepare, 'TARGET', target), \
                    mock.patch.object(prepare, 'supervisor_mqtt', return_value=dict(self.SERVICE)):
                self.assertEqual(prepare.main(), 0)
            self.assertEqual(oct(target.stat().st_mode & 0o777), '0o600')
            cfg = reader.load_config(target)
            self.assertEqual(cfg['local_mqtt']['host'], self.SERVICE['host'])
            self.assertEqual(cfg['device_sn'], 'TESTSN')

    def test_main_fails_cleanly_when_options_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(prepare, 'OPTIONS', Path(directory) / 'absent.json'):
                self.assertEqual(prepare.main(), 1)


class AddonMetadataTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((ROOT / 'config.yaml').read_text())

    def test_version_matches_the_code(self):
        self.assertEqual(self.config['version'], reader.__version__)

    def test_every_option_has_a_schema_entry_and_the_collector_understands_it(self):
        self.assertEqual(set(self.config['options']), set(self.config['schema']))
        known = (set(prepare.DEFAULTS) - {'api_host'}) | {'email', 'password', 'device_sn', 'local_mqtt'}
        self.assertEqual(set(self.config['options']), known)
        self.assertEqual(self.config['options']['freshness_seconds'], 180)

    def test_mqtt_service_is_optional_and_device_serial_is_not_preset(self):
        self.assertEqual(self.config['services'], ['mqtt:want'])
        self.assertEqual(self.config['options']['device_sn'], '')
        self.assertEqual(self.config['options']['local_mqtt']['host'], '')

    def test_docker_context_ships_every_file_the_image_copies(self):
        copied = re.search(r'^COPY ((?:[\w.-]+ )+)\./$', (ROOT / 'Dockerfile').read_text(), re.M).group(1).split()
        allowed = (ROOT / '.dockerignore').read_text().split()
        for name in copied:
            self.assertTrue((ROOT / name).is_file(), name)
            self.assertIn('!' + name, allowed, name)


class InputTag:
    def __init__(self, name):
        self.name = name


class BlueprintLoader(yaml.SafeLoader):
    pass


BlueprintLoader.add_constructor('!input', lambda loader, node: InputTag(loader.construct_scalar(node)))


class BlueprintTests(unittest.TestCase):
    PATH = REPO / 'blueprints' / 'automation' / 'azman0101' / 'scheduled_charge_window.yaml'

    def setUp(self):
        self.text = self.PATH.read_text()
        self.doc = yaml.load(self.text, Loader=BlueprintLoader)
        self.meta = self.doc['blueprint']

    def inputs_used(self, node):
        if isinstance(node, InputTag):
            yield node.name
        elif isinstance(node, dict):
            for value in node.values():
                yield from self.inputs_used(value)
        elif isinstance(node, list):
            for value in node:
                yield from self.inputs_used(value)

    def test_metadata_and_import_url_point_at_this_file(self):
        self.assertEqual(self.meta['domain'], 'automation')
        self.assertTrue(self.meta['source_url'].startswith('https://github.com/azman0101/ha-ecoflow/blob/main/'))
        self.assertTrue(self.meta['source_url'].endswith(str(self.PATH.relative_to(REPO))))

    def test_inputs_defined_and_used_match(self):
        defined = set(self.meta['input'])
        used = set(self.inputs_used({k: v for k, v in self.doc.items() if k != 'blueprint'}))
        self.assertEqual(defined, used)

    def test_nothing_personal_or_vendor_specific_is_hard_coded(self):
        self.assertNotIn('aqara', self.text.lower())
        body = yaml.dump({k: v for k, v in self.doc.items() if k != 'blueprint'}, Dumper=yaml.SafeDumper) \
            if False else self.text.split('\ntriggers:')[1]
        self.assertIsNone(re.search(r'\b(switch|sensor|binary_sensor|input_boolean)\.[a-z0-9_]+', body))

    def test_end_of_window_always_turns_the_switch_off(self):
        branch = self.doc['actions'][0]['choose'][0]
        self.assertEqual(branch['conditions'], [{'condition': 'trigger', 'id': 'end'}])
        self.assertEqual([a['action'] for a in branch['sequence']], ['homeassistant.turn_off'])
        self.assertEqual(self.doc['conditions'], [])

    def test_start_turns_on_unless_the_target_is_already_reached(self):
        branch = self.doc['actions'][0]['choose'][1]
        inner = branch['sequence'][0]
        self.assertEqual(inner['choose'][0]['conditions'][0]['state'], 'on')
        self.assertEqual(inner['choose'][0]['sequence'][0]['action'], 'homeassistant.turn_off')
        self.assertEqual(inner['default'][0]['action'], 'homeassistant.turn_on')

    def test_early_stop_requires_window_switch_on_and_a_confirmed_target(self):
        branch = self.doc['actions'][0]['choose'][2]
        kinds = [c['condition'] for c in branch['conditions']]
        self.assertEqual(kinds, ['trigger', 'time', 'state', 'state'])
        self.assertEqual(branch['conditions'][0]['id'], ['target', 'recheck'])
        confirmed = branch['conditions'][3]
        self.assertEqual(confirmed['state'], 'on')
        self.assertIn('minutes', confirmed['for'])
        self.assertEqual([a['action'] for a in branch['sequence']], ['homeassistant.turn_off'])

    def test_every_trigger_id_is_handled(self):
        ids = {t['id'] for t in self.doc['triggers']}
        self.assertEqual(ids, {'start', 'end', 'target', 'recheck'})
        handled = {'end', 'start', 'target', 'recheck'}
        self.assertEqual(ids, handled)

    def test_state_trigger_waits_for_the_confirmation_delay(self):
        trigger = next(t for t in self.doc['triggers'] if t['id'] == 'target')
        self.assertEqual(trigger['to'], 'on')
        self.assertIsInstance(trigger['for']['minutes'], InputTag)


if __name__ == '__main__':
    unittest.main()
