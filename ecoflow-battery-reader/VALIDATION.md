# Validation

## 1.1.0 — 11 octobre 2026

Vérifié :
- 62 tests hors ligne (décodage, fraîcheur, états dérivés, payloads de découverte, préparation des options, blueprint, absence de numéro de série réel).
- Test de bout en bout du vrai collecteur contre un **broker MQTT local** (`amqtt`) : découverte publiée à la connexion (12 composants, non retenue), états publiés sans RETAIN, découverte renvoyée à la réception de `homeassistant/status = online`, SOC périmé ⇒ `charge_target_reached` non publié et `telemetry_fresh = OFF`, disponibilité `offline` à la perte du cloud.
- Noms de champs de la découverte par appareil confirmés dans la documentation MQTT de Home Assistant.
- `bandit` (gravité moyenne et plus), `ruff`, `pip-audit`, build Docker et linter d'add-on en CI.

Contrôles complémentaires du 11 octobre 2026 :
- `pip-audit -r requirements.txt` : aucune vulnérabilité connue.
- `bandit -ll ecoflow_battery.py ecoflow_discovery.py prepare_config.py` : aucune alerte medium/high.

**Non vérifié** (aucune instance Home Assistant n'était disponible) :
- création effective des entités et de l'appareil par Home Assistant ;
- récupération des identifiants via le service `mqtt` du Supervisor ;
- exécution du blueprint dans Home Assistant (structure et logique vérifiées par tests uniquement) ;
- aucun essai avec le cloud EcoFlow réel pour cette version.

## 1.0.0 — 11 octobre 2026

## Vérifications réussies

- 28 tests hors ligne du collecteur, du Protobuf et des templates/conditions YAML.
- Test MQTT EcoFlow réel en `--observe --duration 45` : authentification applicative, certificat MQTT, abonnement et snapshot en lecture seule.
- 26 messages reçus, une requête snapshot, zéro erreur de décodage.
- SOC observé : 89 %, puis 88,995 % ; plafond : 90 %.
- Aucun topic `property/set` utilisé. Aucune connexion à un broker MQTT de production pendant ce test.
- Vérification de la protection des publications cloud : seuls les topics de lecture fixés par le client sont acceptés ; une publication retenue ou vers `property/set` est refusée.
- Source Protobuf figée dans le livrable, vérifiée par SHA-256, licence amont conservée.

## Vérifications restant sur l'installation cible

- Construire et démarrer le conteneur avec les identifiants du broker MQTT du HA qui gère cette batterie.
- Vérifier/recharger la configuration avec la version HA installée ; les tests Jinja ne remplacent pas ce contrôle.
- Vérifier les identifiants d'entités réels et la prise Aqara.
- Observer la collecte dans la durée et contrôler une trace de recharge naturelle.

Aucun déploiement permanent, redémarrage HA ou commande de prise/batterie n'a été effectué pendant la création de ces livrables.
