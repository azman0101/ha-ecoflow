# Validation — 11 octobre 2026

## Vérifications réussies

- 28 tests hors ligne du collecteur, du Protobuf et des templates/conditions YAML.
- Test MQTT EcoFlow réel en `--observe --duration 45` : authentification applicative, certificat MQTT, abonnement et snapshot en lecture seule.
- 26 messages reçus, une requête snapshot, zéro erreur de décodage.
- SOC observé : 89 %, puis 88,995 % ; plafond : 90 %.
- Aucun topic `property/set` utilisé. Aucune connexion au broker MQTT du HA du NVR ou de l'autre HA pendant ce test.
- Vérification de la protection des publications cloud : seuls les topics de lecture fixés par le client sont acceptés ; une publication retenue ou vers `property/set` est refusée.
- Source Protobuf figée dans le livrable, vérifiée par SHA-256, licence amont conservée.

## Vérifications restant sur l'installation cible

- Construire et démarrer le conteneur avec les identifiants du broker MQTT du HA qui gère cette batterie.
- Vérifier/recharger la configuration avec la version HA installée ; les tests Jinja ne remplacent pas ce contrôle.
- Vérifier les identifiants d'entités réels et la prise Aqara.
- Observer la collecte dans la durée et contrôler une trace de recharge naturelle.

Aucun déploiement permanent, redémarrage HA ou commande de prise/batterie n'a été effectué pendant la création de ces livrables.
