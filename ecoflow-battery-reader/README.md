# EcoFlow DELTA 3 Reader

Collecteur permanent qui lit l'état d'une **EcoFlow DELTA 3 Classic** via l'API cloud *applicative* d'EcoFlow (MQTT + Protobuf) et le publie sur le broker MQTT de Home Assistant. Les entités sont créées automatiquement par la **découverte MQTT** : aucun YAML à copier.

> Projet non officiel, entièrement généré par IA, sans affiliation avec EcoFlow — voir le [README du dépôt](../README.md) avant de lui confier vos identifiants.

## 1. Fonctionnement

```text
Compte EcoFlow (e-mail / mot de passe)
    → login applicatif HTTPS + certificat MQTT conservé en mémoire
    → MQTT EcoFlow (TLS 8883), messages Protobuf
    → collecteur Python permanent
    → broker MQTT de Home Assistant : mesures JSON + annonce des entités (discovery)
    → appareil « EcoFlow DELTA 3 » dans Home Assistant
```

Le collecteur utilise les topics applicatifs `/app/device/property/{sn}`, `/app/{userId}/{sn}/thing/property/get_reply` et `/app/{userId}/{sn}/thing/property/get`, comme le [client applicatif de l'intégration EcoFlow Cloud](https://github.com/tolwi/hassio-ecoflow-cloud/blob/main/custom_components/ecoflow_cloud/api/private_api.py). Il demande un *snapshot* en lecture seule après l'abonnement puis toutes les 60 s (la télémétrie spontanée seule peut rester silencieuse plus d'une minute). Le client cloud refuse toute publication autre que cette requête vide : **pas de `property/set`**, aucune commande envoyée à la batterie.

## 2. Configuration du module

| Option | Défaut | Rôle |
|---|---|---|
| `email`, `password` | — | Compte EcoFlow (celui de l'application mobile). |
| `device_sn` | — | Numéro de série de la batterie (dans l'application EcoFlow). |
| `local_mqtt.host` | *(vide)* | **Vide = broker MQTT fourni par le Supervisor** (généralement Mosquitto), sans identifiants à saisir. Renseigné = broker manuel. |
| `local_mqtt.port`, `username`, `password`, `tls` | 1883, —, —, non | Uniquement pour un broker manuel. |
| `discovery` | oui | Annonce les entités à Home Assistant (découverte MQTT). |
| `discovery_prefix` | `homeassistant` | Préfixe de découverte de l'intégration MQTT de Home Assistant. |
| `target_margin` | 0,2 | Marge (points de %) du capteur *Charge cible atteinte* : vrai quand `SOC ≥ plafond de charge − marge`. |
| `topic_prefix` | `ecoflow/delta3classic` | Préfixe des topics de mesures. |
| `instance_id` | `ecoflow-bridge` | Identifiant client ; un seul collecteur par batterie. |
| `snapshot_interval` | 60 | Secondes entre deux demandes de lecture (60 à 3600). |
| `freshness_seconds` | 180 | Doit rester à 180 (même borne que `expire_after`). |

Si `local_mqtt.host` est vide et qu'aucun broker n'est disponible, le module s'arrête avec un message explicite : installez le module Mosquitto ou renseignez `local_mqtt`.

## 3. Entités

Un appareil **EcoFlow DELTA 3** regroupe :

| Entité | Information |
|---|---|
| `sensor.ecoflow_batterie` | SOC global (CMS) en %. Zéro accepté ; jamais remplacé par le SOC d'une batterie secondaire. |
| `sensor.ecoflow_plafond_charge` | Plafond de charge en % (diagnostic). |
| `sensor.ecoflow_seuil_decharge` | Seuil minimal de décharge en % (diagnostic). |
| `sensor.ecoflow_puissance_entree` / `_sortie` / `_secteur` / `_solaire` | Puissances en W, si le firmware les transmet. |
| `sensor.ecoflow_etat_charge_brut` | Code reçu (diagnostic ; conserve par exemple `-1`). |
| `sensor.ecoflow_etat_charge` | `idle`, `discharging`, `charging` ou `unknown` : seuls 0/1/2 sont interprétés. |
| `binary_sensor.ecoflow_collecteur_connecte` | Collecteur connecté au cloud EcoFlow. Ne prouve pas que la batterie publie encore. |
| `binary_sensor.ecoflow_telemetrie_recente` | SOC valide reçu depuis moins de 3 minutes. |
| `binary_sensor.ecoflow_charge_cible_atteinte` | `SOC ≥ plafond − marge`, uniquement si SOC **et** plafond sont frais ; sinon *indisponible*. |

Les temps d'autonomie/charge et les sorties individuelles ne sont pas exposés : leur sémantique n'est pas validée (une capture a donné un état `-1` et des temps bruts `5939`/`3547`), et on ne transforme pas ces valeurs par supposition.

### Fraîcheur et sécurité des mesures

- Chaque mesure porte son propre instant de réception : un message ne contenant que des puissances **ne rafraîchit pas** le SOC.
- Les mesures sont publiées **sans RETAIN** et les capteurs expirent après 180 s (`expire_after`) : Home Assistant n'affiche jamais une ancienne valeur comme actuelle.
- Les capteurs binaires dérivés sont calculés **par le collecteur**. *Charge cible atteinte* n'est publié que si le SOC et le plafond sont frais ; une mesure absente, invalide ou périmée la rend *indisponible*, jamais « atteinte ». Si le collecteur s'arrête, le Last Will met tout en *indisponible*.
- Seule la disponibilité du collecteur utilise RETAIN (avec un Last Will `offline`).
- La découverte n'est pas retenue (approche recommandée par Home Assistant) : elle est renvoyée à chaque connexion et à chaque message de naissance `homeassistant/status`, sans laisser d'entités fantômes à la désinstallation. Si vous avez désactivé le message de naissance dans l'intégration MQTT, redémarrez le module après un redémarrage de Home Assistant.

## 4. Recharge programmée avec une prise (optionnel)

Piloter une prise pour charger pendant une plage horaire est un usage particulier, **indépendant du module** : il est fourni sous forme de [blueprint](../blueprints/automation/azman0101/scheduled_charge_window.yaml) générique (interrupteur + capteur binaire « cible atteinte » + heures). Importez-le depuis le [README du dépôt](../README.md#recharge-programmée-optionnel-indépendant-du-module) et choisissez vos entités dans l'interface.

Comportement : à l'heure de début, la prise est allumée (sauf si la cible est déjà atteinte) ; pendant la plage, elle est coupée quand la cible reste atteinte pendant le délai de confirmation (2 min par défaut) ; à l'heure de fin, elle est **toujours** coupée, même si MQTT est indisponible. Une cible indisponible n'arrête jamais la charge plus tôt. Hors de la plage horaire, seuls le début et la fin sont traités : il n'y a aucune scrutation périodique, l'automatisation ne se lance donc pas toute la journée. Avec un plafond configuré à 90 %, la cible est 89,8 %, pas 100 %. Si Home Assistant ou la prise est indisponible à l'heure de fin, rien ne garantit la coupure physique : ne comptez pas dessus pour une sécurité critique.

## 5. Migration depuis la 1.0.x

La 1.0.x demandait de copier `homeassistant.yaml` dans `configuration.yaml`. Ces fichiers n'existent plus.

1. Mettez le module à jour (1.1.0) et redémarrez-le.
2. Dans `configuration.yaml`, **supprimez** les blocs `mqtt: sensor/binary_sensor` et `template:` EcoFlow que vous aviez copiés, puis redémarrez Home Assistant. Les entités gardent leur identifiant et leur historique (mêmes `unique_id`).
3. Les deux anciens capteurs *template* (`telemetrie_recente`, `charge_cible_atteinte`) sont remplacés par des entités MQTT du même nom. Si Home Assistant les a suffixées en `_2`, supprimez les entités orphelines dans *Paramètres → Appareils et services → Entités* (filtre « ecoflow »), puis renommez.
4. Remplacez votre ancienne automatisation par le blueprint (section 4) et désactivez l'ancienne.
5. Si l'utilisateur MQTT du module est restreint par des ACL : autorisez l'écriture sous `<discovery_prefix>/device/#` et la lecture de `<discovery_prefix>/status`, en plus de `ecoflow/delta3classic/#`.

## 6. Hors Home Assistant OS (Docker)

Sans Supervisor (Home Assistant Container/Core), lancez le conteneur avec `compose.yaml`. Créez `private/ecoflow.json` en mode `600` à partir de `credentials.example.json` (broker **renseigné obligatoirement**, la détection automatique n'existe qu'avec le Supervisor) et montez-le en lecture seule. Les options `discovery`, `discovery_prefix` et `target_margin` sont les mêmes.

```bash
docker compose build
docker compose run --rm ecoflow-mqtt --config /run/secrets/ecoflow.json --observe --duration 90   # lecture seule, ne publie rien
docker compose up -d
docker compose logs --tail=30 -f ecoflow-mqtt
```

`--observe` n'écrit rien sur le broker local ; `--passive` ne demande pas de snapshot (déconseillé en service). Chaque collecteur doit avoir son `instance_id`. Les journaux Docker sont limités à 3 fichiers de 5 Mo.

## 7. Dépannage

| Symptôme | Vérification |
|---|---|
| Aucun appareil dans Home Assistant | Intégration MQTT connectée au même broker, découverte activée, `discovery_prefix` identique ; ACL en écriture sur `<prefix>/device/#`. |
| Le module s'arrête : `local_mqtt.host is empty…` | Installer/démarrer Mosquitto, ou renseigner `local_mqtt`. |
| Authentification refusée | Compte applicatif et mot de passe exacts, serveur régional. Les AccessKey du portail développeur ne sont pas utilisées. |
| MQTT accepté mais aucun SOC | Requêtes snapshot, réponses `get_reply`, firmware/modèle, `decode_errors` dans le heartbeat. |
| Entités *indisponibles* | Collecteur arrêté ou aucune mesure fraîche depuis 3 minutes (comportement voulu). |
| *Charge cible atteinte* indisponible | SOC ou plafond non frais : le capteur ne devient pas « atteinte » par défaut. |
| `descriptor_hash_mismatch` | Descripteur absent ou modifié ; réinstaller le module. |

## 8. Tests

```bash
python3 -m venv .venv-tests
.venv-tests/bin/python -m pip install -r requirements-test.txt
.venv-tests/bin/python -B -m unittest -v test_ecoflow_battery.py
```

Ils couvrent le décodage Protobuf, la fraîcheur, les états dérivés, les payloads de découverte (dont la stabilité des `unique_id`), la préparation des options, le blueprint et l'absence de numéro de série réel dans le dépôt. Voir `VALIDATION.md` pour ce qui a et n'a pas été vérifié en conditions réelles.
