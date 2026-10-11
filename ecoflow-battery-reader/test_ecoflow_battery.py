"""Offline tests: synthetic protobuf, fake MQTT clients, YAML/Jinja safety checks."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import ecoflow_battery as reader

CFG = {'api_host': 'https://api-e.ecoflow.com', 'email': 'test@example.invalid', 'password': 'TESTPASSWORD',
       'device_sn': 'TESTSN', 'instance_id': 'test-instance', 'snapshot_interval': 60,
       'freshness_seconds': 180, 'topic_prefix': 'ecoflow/delta3classic',
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


class TemplateTests(unittest.TestCase):
    def setUp(self):
        import yaml
        from jinja2 import Environment, StrictUndefined
        root = Path(__file__).parent
        self.ha = yaml.safe_load((root / 'homeassistant.yaml').read_text())
        self.automation = yaml.safe_load((root / 'automations.yaml').read_text())[0]
        self.ui = yaml.safe_load((root / 'automation-ui.yaml').read_text())
        self.now = datetime.now(timezone.utc)
        self.data = {'sensor.ecoflow_batterie': '89.9', 'sensor.ecoflow_plafond_charge': '90',
                     'binary_sensor.ecoflow_collecteur_connecte': 'on',
                     'binary_sensor.ecoflow_telemetrie_recente': 'on'}
        self.attrs = {'sensor.ecoflow_batterie': {'received_at': self.now.timestamp()-2},
                      'sensor.ecoflow_plafond_charge': {'received_at': self.now.timestamp()-2}}
        self.full = SimpleNamespace(state='on', last_changed=self.now-timedelta(seconds=130))
        class States:
            def __call__(obj, entity):
                return self.data.get(entity, 'unknown')
            @property
            def binary_sensor(obj):
                return SimpleNamespace(ecoflow_charge_cible_atteinte=self.full)
        def is_number(value):
            try:
                import math
                return not isinstance(value, bool) and math.isfinite(float(value))
            except (TypeError, ValueError):
                return False
        def as_timestamp(value, default=None):
            try:
                return value.timestamp() if isinstance(value, datetime) else float(value)
            except (TypeError, ValueError):
                return default
        self.env = Environment(undefined=StrictUndefined)
        self.env.globals.update(states=States(), state_attr=lambda entity, key: self.attrs.get(entity, {}).get(key),
                                is_state=lambda entity, value: self.data.get(entity) == value,
                                is_number=is_number, now=lambda: self.now, as_timestamp=as_timestamp)
        binary = self.ha['template'][0]['binary_sensor']
        self.fresh = binary[0]
        self.full_template = binary[1]
        choices = self.automation['actions'][0]['choose']
        self.already_full = choices[1]['sequence'][0]['choose'][0]['conditions'][0]['value_template']
        self.stop_early = choices[2]['conditions'][-1]['value_template']

    def truth(self, template):
        return self.env.from_string(template).render().strip() == 'True'

    def test_stop_near_configured_90_not_100(self):
        self.assertTrue(self.truth(self.full_template['availability']))
        self.assertTrue(self.truth(self.full_template['state']))
        self.assertTrue(self.truth(self.already_full))
        self.assertTrue(self.truth(self.stop_early))
        self.data['sensor.ecoflow_batterie'] = '89.04'
        self.assertFalse(self.truth(self.full_template['state']))
        self.assertFalse(self.truth(self.stop_early))

    def test_zero_never_stops_charge(self):
        self.data['sensor.ecoflow_batterie'] = '0'
        self.assertTrue(self.truth(self.fresh['state']))
        self.assertTrue(self.truth(self.full_template['availability']))
        self.assertFalse(self.truth(self.full_template['state']))
        self.assertFalse(self.truth(self.stop_early))

    def test_stale_either_metric_blocks_early_cutoff(self):
        for entity in ('sensor.ecoflow_batterie', 'sensor.ecoflow_plafond_charge'):
            self.attrs[entity]['received_at'] = self.now.timestamp()-180
            self.assertFalse(self.truth(self.full_template['availability']))
            self.assertFalse(self.truth(self.already_full))
            self.assertFalse(self.truth(self.stop_early))
            self.attrs[entity]['received_at'] = self.now.timestamp()-2

    def test_missing_future_and_invalid_soc_blocks_cutoff(self):
        for value in ('unavailable', 'unknown', '-1', '101', 'NaN'):
            self.data['sensor.ecoflow_batterie'] = value
            self.assertFalse(self.truth(self.full_template['availability']))
            self.assertFalse(self.truth(self.stop_early))
        self.data['sensor.ecoflow_batterie'] = '90'
        self.attrs['sensor.ecoflow_batterie']['received_at'] = self.now.timestamp()+1
        self.assertFalse(self.truth(self.stop_early))

    def test_transport_disconnect_blocks_cutoff(self):
        self.data['binary_sensor.ecoflow_collecteur_connecte'] = 'off'
        self.assertFalse(self.truth(self.fresh['state']))
        self.assertFalse(self.truth(self.already_full))
        self.assertFalse(self.truth(self.stop_early))

    def test_two_minutes_confirmation_required(self):
        self.full.last_changed = self.now-timedelta(seconds=119)
        self.assertFalse(self.truth(self.stop_early))
        self.full.last_changed = self.now-timedelta(seconds=120)
        self.assertTrue(self.truth(self.stop_early))
        self.full = None
        self.assertFalse(self.truth(self.stop_early))

    def test_0420_cutoff_independent_of_mqtt(self):
        choice = self.automation['actions'][0]['choose'][0]
        self.assertEqual(choice['conditions'], [{'condition': 'trigger', 'id': 'eteindre'}])
        self.assertEqual(choice['sequence'][0]['action'], 'switch.turn_off')
        trigger = next(t for t in self.automation['triggers'] if t['id'] == 'eteindre')
        self.assertEqual(trigger['at'], '04:20:00')
        self.assertEqual(self.automation['conditions'], [])

    def test_ui_and_file_automation_identical(self):
        self.assertEqual({k:v for k,v in self.automation.items() if k != 'id'}, self.ui)

    def test_no_retained_measurement_reliance_and_topics_match(self):
        sensors = self.ha['mqtt']['sensor']
        self.assertEqual(len(sensors), 9)
        for sensor in sensors:
            self.assertEqual(sensor['expire_after'], 180)
            key = sensor['state_topic'].split('/')[-1]
            self.assertIn(key, list(reader.FIELDS)+['charge_state'])
            self.assertIn('received_at', sensor['json_attributes_template'])
        # All string templates in the delivered YAML must parse.
        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str) and ('{{' in value or '{%' in value):
                self.env.parse(value)
        walk(self.ha)
        walk(self.automation)


if __name__ == '__main__':
    unittest.main()
