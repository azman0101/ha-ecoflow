# Changelog

## [1.1.0] - 2026-10-11
### Ajouté
- **Découverte MQTT** : un appareil « EcoFlow DELTA 3 » et ses entités sont créés automatiquement ; plus de YAML à copier dans `configuration.yaml`. Les `unique_id` et identifiants d'entités de la 1.0.x sont conservés.
- **Broker MQTT détecté automatiquement** via le service `mqtt` du Supervisor : laisser `local_mqtt.host` vide.
- Capteurs binaires *Télémétrie récente* et *Charge cible atteinte* calculés par le collecteur (marge configurable : `target_margin`).
- Options `discovery`, `discovery_prefix`, `target_margin`.
- **Blueprint** générique `scheduled_charge_window` (plage horaire + arrêt anticipé), indépendant du module et de toute marque de prise.

### Supprimé
- `homeassistant.yaml`, `automations.yaml`, `automation-ui.yaml` (remplacés par la découverte MQTT et le blueprint). Voir « Migration depuis la 1.0.x » dans le README du module.
- Les valeurs par défaut personnelles de `device_sn` et de `local_mqtt`.

### Technique
- Architectures prises en charge : `amd64` et `aarch64` uniquement.
- Image pré-construite publiée sur GHCR.

## [1.0.0] - 2026-10-11
- Version initiale du module complémentaire pour EcoFlow DELTA 3 Classic.
- Support multi-architectures (amd64, aarch64, armv7, etc.).
- Connexion sécurisée au cloud EcoFlow et publication sur Mosquitto local.
