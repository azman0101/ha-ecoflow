# EcoFlow DELTA 3 Reader

Collecte en continu l'état d'une batterie EcoFlow DELTA 3 Classic via l'API cloud applicative d'EcoFlow (MQTT Protobuf) et le publie sur le broker MQTT de Home Assistant. Les entités sont créées **automatiquement** (découverte MQTT) : rien à écrire dans `configuration.yaml`.

## Démarrage rapide

1. Installez et démarrez le broker MQTT fourni par le Supervisor (généralement l'add-on **Mosquitto broker**), puis vérifiez que l'intégration **MQTT** de Home Assistant est configurée (Home Assistant la propose automatiquement).
2. Dans l'onglet **Configuration** de ce module :
   - **email** / **password** : votre compte EcoFlow (celui de l'application mobile) ;
   - **device_sn** : numéro de série de la batterie (dans l'application EcoFlow, ex. `P321XXXXXXXXXXXX`) ;
   - laissez **local_mqtt.host vide** pour utiliser automatiquement le broker MQTT fourni par le Supervisor.
3. Enregistrez et démarrez. L'appareil **EcoFlow DELTA 3** apparaît dans *Paramètres → Appareils et services → MQTT*.

## Options

| Option | Défaut | Rôle |
|---|---|---|
| `local_mqtt.host` | vide | Vide : broker fourni par le Supervisor. Sinon broker manuel (avec `port`, `username`, `password`, `tls`). |
| `discovery` | oui | Annonce les entités à Home Assistant. |
| `discovery_prefix` | `homeassistant` | Préfixe de découverte de l'intégration MQTT. |
| `target_margin` | 0,2 | Marge du capteur *Charge cible atteinte* : vrai quand `SOC ≥ plafond de charge − marge`. |
| `snapshot_interval` | 60 | Secondes entre deux lectures (60 à 3600). |

Les autres options (`topic_prefix`, `instance_id`, `freshness_seconds`) ne se modifient normalement pas.

## Recharge programmée avec une prise

Besoin optionnel et indépendant de ce module : un **blueprint** générique pilote n'importe quel interrupteur selon une plage horaire et un capteur « cible atteinte ». Importez-le depuis le [README du dépôt](https://github.com/azman0101/ha-ecoflow#recharge-programmée-optionnel-indépendant-du-module).

## Transparence

Ce module est **entièrement généré par IA** et n'est pas affilié à EcoFlow. Il utilise l'API cloud applicative non documentée d'EcoFlow en lecture seule. Relisez le code avant utilisation — voir le [README du dépôt](https://github.com/azman0101/ha-ecoflow#️-transparence--code-100--généré-par-ia).

Documentation complète, migration depuis la 1.0.x et dépannage : [README du module](https://github.com/azman0101/ha-ecoflow/tree/main/ecoflow-battery-reader).
