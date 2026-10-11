"""Home Assistant MQTT device discovery payload for the EcoFlow DELTA 3 reader.

Pure functions, no network access: they only build the JSON document published on
``<discovery_prefix>/device/<node_id>/config`` (not retained; re-sent on Home Assistant's birth message).

``unique_id`` and ``default_entity_id`` values are the ones used by the
hand-written YAML shipped with 1.0.x, so entities of an existing installation
keep their entity IDs and history once the YAML is removed.
"""
import re

PROJECT_URL = 'https://github.com/azman0101/ha-ecoflow'
VALUE_TEMPLATE = '{{ value_json.value }}'
ATTRIBUTES_TEMPLATE = "{{ {'received_at': value_json.received_at, 'source': value_json.source} | tojson }}"

# key: (platform, name, unique_id, default_entity_id, extra component options)
ENTITIES = {
    'soc': ('sensor', 'Batterie', 'ecoflow_classic_mqtt_soc_v1', 'sensor.ecoflow_batterie',
            {'unit_of_measurement': '%', 'state_class': 'measurement', 'device_class': 'battery'}),
    'charge_limit': ('sensor', 'Plafond de charge', 'ecoflow_classic_mqtt_charge_limit_v1',
                     'sensor.ecoflow_plafond_charge',
                     {'unit_of_measurement': '%', 'state_class': 'measurement', 'entity_category': 'diagnostic'}),
    'discharge_limit': ('sensor', 'Seuil de décharge', 'ecoflow_classic_mqtt_discharge_limit_v1',
                        'sensor.ecoflow_seuil_decharge',
                        {'unit_of_measurement': '%', 'state_class': 'measurement', 'entity_category': 'diagnostic'}),
    'power_in': ('sensor', 'Puissance entrée', 'ecoflow_classic_mqtt_power_in_v1',
                 'sensor.ecoflow_puissance_entree',
                 {'unit_of_measurement': 'W', 'state_class': 'measurement', 'device_class': 'power'}),
    'power_out': ('sensor', 'Puissance sortie', 'ecoflow_classic_mqtt_power_out_v1',
                  'sensor.ecoflow_puissance_sortie',
                  {'unit_of_measurement': 'W', 'state_class': 'measurement', 'device_class': 'power'}),
    'power_ac_in': ('sensor', 'Puissance secteur', 'ecoflow_classic_mqtt_power_ac_in_v1',
                    'sensor.ecoflow_puissance_secteur',
                    {'unit_of_measurement': 'W', 'state_class': 'measurement', 'device_class': 'power'}),
    'power_pv': ('sensor', 'Puissance solaire', 'ecoflow_classic_mqtt_power_pv_v1',
                 'sensor.ecoflow_puissance_solaire',
                 {'unit_of_measurement': 'W', 'state_class': 'measurement', 'device_class': 'power'}),
    'charge_state_code': ('sensor', 'État de charge (brut)', 'ecoflow_classic_mqtt_charge_state_code_v1',
                          'sensor.ecoflow_etat_charge_brut', {'entity_category': 'diagnostic'}),
    'charge_state': ('sensor', 'État de charge', 'ecoflow_classic_mqtt_charge_state_v1',
                     'sensor.ecoflow_etat_charge', {}),
    # Computed by the collector from per-measurement ages (see Bridge.derived_states).
    'telemetry_fresh': ('binary_sensor', 'Télémétrie récente', 'ecoflow_classic_telemetry_fresh_v1',
                        'binary_sensor.ecoflow_telemetrie_recente',
                        {'device_class': 'connectivity', 'entity_category': 'diagnostic'}),
    'charge_target_reached': ('binary_sensor', 'Charge cible atteinte', 'ecoflow_classic_charge_target_reached_v1',
                              'binary_sensor.ecoflow_charge_cible_atteinte', {}),
}
# Reflects the collector's own MQTT availability topic (online/offline), not a measurement.
COLLECTOR_CONNECTED = ('binary_sensor', 'Collecteur connecté', 'ecoflow_classic_mqtt_connection_v1',
                       'binary_sensor.ecoflow_collecteur_connecte',
                       {'device_class': 'connectivity', 'entity_category': 'diagnostic'})

DISCOVERY_PREFIX_RE = re.compile(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*')


def node_id(cfg):
    """Stable, topic-safe identifier of the physical battery (device_sn is validated alphanumeric)."""
    return 'ecoflow_' + cfg['device_sn'].lower()


def discovery_topic(cfg):
    return '%s/device/%s/config' % (cfg['discovery_prefix'], node_id(cfg))


def status_topic(cfg):
    """Home Assistant publishes ``online`` here at start-up (MQTT birth message)."""
    return cfg['discovery_prefix'] + '/status'


def build_payload(cfg, version):
    prefix = cfg['topic_prefix']
    availability = {'availability_topic': prefix + '/availability', 'payload_available': 'online',
                    'payload_not_available': 'offline'}
    components = {}
    for key, (platform, name, unique_id, entity_id, extra) in ENTITIES.items():
        component = {'platform': platform, 'name': name, 'unique_id': unique_id, 'default_entity_id': entity_id,
                     'state_topic': '%s/%s' % (prefix, key), 'expire_after': cfg['freshness_seconds'],
                     'qos': 1, **availability, **extra}
        if platform == 'sensor':
            component.update(value_template=VALUE_TEMPLATE, json_attributes_topic=component['state_topic'],
                             json_attributes_template=ATTRIBUTES_TEMPLATE)
        components[key] = component
    platform, name, unique_id, entity_id, extra = COLLECTOR_CONNECTED
    components['collector_connected'] = {
        'platform': platform, 'name': name, 'unique_id': unique_id, 'default_entity_id': entity_id,
        'state_topic': prefix + '/availability', 'payload_on': 'online', 'payload_off': 'offline', 'qos': 1, **extra}
    return {
        'device': {'identifiers': [node_id(cfg)], 'name': 'EcoFlow DELTA 3', 'manufacturer': 'EcoFlow',
                   'model': 'DELTA 3 Classic'},
        'origin': {'name': 'EcoFlow DELTA 3 Reader', 'sw_version': version, 'support_url': PROJECT_URL},
        'components': components,
    }
