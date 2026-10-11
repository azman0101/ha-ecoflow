# EcoFlow DELTA 3 Battery Reader

Module complémentaire Home Assistant pour collecter en continu l'état de la batterie EcoFlow DELTA 3 via l'API cloud applicative (MQTT Protobuf) et la republier sur le broker MQTT local de Home Assistant.

## Configuration

Rendez-vous dans l'onglet **Configuration** du module complémentaire :

1. **email** : Votre adresse email EcoFlow (identique à l'application mobile EcoFlow).
2. **password** : Votre mot de passe EcoFlow.
3. **device_sn** : Numéro de série de la batterie (visible dans l'application EcoFlow, ex. `P321XXXXXXXXXXXX`).
4. **local_mqtt** :
   - `host` : `core-mosquitto` (par défaut pour le broker Mosquitto de HA) ou l'IP de HA.
   - `port` : `1883`
   - `username` : Nom d'utilisateur pour Mosquitto (ex: `homeassistant`).
   - `password` : Mot de passe de l'utilisateur Mosquitto.

## Capteurs Home Assistant

Ajoutez la configuration des capteurs dans votre `configuration.yaml` (fichier `homeassistant.yaml` du dépôt).

## Transparence

Ce module est **entièrement généré par IA** et n'est pas affilié à EcoFlow. Il utilise l'API cloud applicative non documentée d'EcoFlow en lecture seule. Relisez le code avant utilisation — voir le [README du dépôt](https://github.com/azman0101/ha-ecoflow#️-transparence--code-100--généré-par-ia).
