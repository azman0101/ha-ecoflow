# Batterie EcoFlow via MQTT applicatif — collecteur et autre Home Assistant

Cette version remplace le lecteur HTTP par un collecteur MQTT permanent. Elle s'adresse au Home Assistant qui gère la batterie et la prise intelligente (exemple fourni avec une prise Aqara).

La batterie concernée est la **DELTA 3 Classic**, numéro de série à renseigner dans la configuration. L'API développeur HTTP renvoie `1006`, mais l'authentification applicative et la lecture MQTT ont été testées avec succès.

## 1. Architecture et différence avec /quota et /status

```text
Compte EcoFlow (e-mail / mot de passe)
    → login applicatif HTTPS + certificat MQTT en mémoire
    → MQTT EcoFlow sur TLS 8883, messages Protobuf
    → collecteur Python permanent
    → broker MQTT du HA cible, mesures JSON
    → capteurs MQTT HA + automatisation de la prise Aqara
```

Les topics `/open/{account}/{sn}/quota` et `/open/{account}/{sn}/status`, avec des noms JSON comme `cmsBattSoc`, concernent le MQTT public développeur. Le test réussi utilise **l'API applicative** :

- `/app/device/property/{sn}` pour la télémétrie spontanée ;
- `/app/{userId}/{sn}/thing/property/get_reply` pour les réponses de lecture ;
- `/app/{userId}/{sn}/thing/property/get` pour demander un snapshot.

Le collecteur utilise ces topics, conformément au [client applicatif EcoFlow Cloud](https://github.com/tolwi/hassio-ecoflow-cloud/blob/main/custom_components/ecoflow_cloud/api/private_api.py). Il ne tente pas d'écouter les topics publics avec les identifiants applicatifs.

Une requête snapshot est envoyée après abonnement, puis toutes les 60 secondes. Elle demande l'état existant ; elle ne change aucun paramètre. Son enveloppe vide reprend la [lecture « get all » de l'intégration DELTA 3](https://github.com/tolwi/hassio-ecoflow-cloud/blob/main/custom_components/ecoflow_cloud/devices/internal/delta3.py). Le client cloud interdit tout autre topic de publication et n'utilise jamais `property/set`. Le collecteur ne contrôle aucune prise.

Cette lecture périodique est nécessaire : le test passif avait reçu 28 messages, mais une seconde connexion était restée silencieuse pendant 75 secondes. Le nouveau test avec snapshot a obtenu immédiatement le SOC et le plafond de charge. Cela valide la lecture ponctuelle, pas encore une journée complète de disponibilité.

## 2. Mesures retenues et limites

| Entité HA attendue | Information | Remarque |
|---|---|---|
| `sensor.ecoflow_batterie` | SOC global CMS en % | Zéro accepté ; aucun remplacement silencieux par le SOC d'une batterie secondaire. |
| `sensor.ecoflow_plafond_charge` | Plafond de charge en % | **90 %** lors des essais. |
| `sensor.ecoflow_seuil_decharge` | Seuil minimal en % | **1 %** dans une trame capturée. |
| `sensor.ecoflow_puissance_entree` | Puissance totale entrante en W | Disponible si le champ est effectivement transmis. |
| `sensor.ecoflow_puissance_sortie` | Puissance totale sortante en W | Même règle. |
| `sensor.ecoflow_puissance_secteur` | Entrée AC en W | Même règle. |
| `sensor.ecoflow_puissance_solaire` | Entrée PV en W | Même règle. |
| `sensor.ecoflow_etat_charge_brut` | Code de fonctionnement reçu | Diagnostic ; conserve notamment `-1`. |
| `sensor.ecoflow_etat_charge` | `idle`, `discharging`, `charging` ou `unknown` | Seuls 0/1/2 sont interprétés ; un autre code reste `unknown`. |
| `binary_sensor.ecoflow_collecteur_connecte` | Collecteur connecté au MQTT cloud et au broker cible | Ne prouve pas que la batterie publie encore. |
| `binary_sensor.ecoflow_telemetrie_recente` | SOC valide reçu depuis moins de trois minutes | Contrôle utile pour la supervision. |
| `binary_sensor.ecoflow_charge_cible_atteinte` | SOC au voisinage du plafond, avec mesures fraîches | Utilisé pour l'arrêt anticipé. |

Les temps d'autonomie/charge, ports multiples et booléens de sorties ne sont pas exposés dans cette version. Ils nécessitent une validation de modèle ou de sémantique : une capture a par exemple fourni un état CMS `-1` et des temps bruts `5939`/`3547`. On ne transforme pas ces valeurs en minutes ou en « charge en cours » par supposition. De même, « différent de 4 » ne suffit pas à garantir qu'une sortie est active lors d'un état transitoire.

Le champ global réellement reçu était `msg32_2_1.cms_batt_soc`. Les champs sont décodés avec le descripteur Protobuf livré et vérifié par SHA-256. Les messages inconnus sont ignorés ; une donnée absente ne devient jamais zéro. Les puissances restent indisponibles jusqu'à leur réception : la présence d'un champ dans le schéma ne prouve pas sa publication par votre firmware.

## 3. Préparer un hôte pour le collecteur

Le collecteur doit rester connecté : **ne pas le lancer toutes les minutes via `command_line`**.

L'option fournie est un petit conteneur Docker sur une machine Linux de l'installation de la batterie. Il fonctionne avec HA Container comme avec HA OS, puisque HA reçoit les données via son broker MQTT. Sur HA OS, utiliser une machine Docker séparée ou un environnement d'extension adapté ; un terminal d'extension laissé ouvert n'est pas un service permanent.

Cloner ce dépôt (ou copier ce dossier) dans un dossier de cette machine, par exemple :

```text
/opt/ecoflow-mqtt/
```

Ce dossier doit contenir au minimum `Dockerfile`, `.dockerignore`, `compose.yaml`, `requirements.txt`, `ecoflow_battery.py`, `delta3_descriptor.bin`, `THIRD_PARTY.md` et `LICENSE.hassio-ecoflow-cloud`.

Le broker MQTT utilisé doit être **celui du HA cible**. Dans HA, configurer l'intégration MQTT pour ce broker si elle n'existe pas. Créer un utilisateur dédié au collecteur avec droit de publication sur :

```text
ecoflow/delta3classic/#
```

Le HA doit pouvoir lire ces topics. Le collecteur ne publie pas de découverte automatique et n'a pas besoin d'accéder aux autres topics de votre installation.

## 4. Créer le fichier privé

Dans le dossier décompressé, exécuter ce snippet depuis un terminal Linux interactif. Il crée `private/ecoflow.json` en mode `600`, sans afficher les secrets ni écraser un fichier existant.

```bash
python3 - <<'PY'
import getpass
import json
import os
from pathlib import Path
import warnings

warnings.simplefilter('error', getpass.GetPassWarning)
folder = Path('private')
folder.mkdir(mode=0o700, exist_ok=True)
folder.chmod(0o700)
path = folder / 'ecoflow.json'
if path.exists() or path.is_symlink():
    raise SystemExit('Fichier déjà présent : arrêt sans écrasement.')
config = {
    'api_host': 'https://api-e.ecoflow.com',
    'email': getpass.getpass('E-mail EcoFlow (masqué) : ').strip(),
    'password': getpass.getpass('Mot de passe EcoFlow : '),
    'device_sn': 'VOTRE_NUMERO_DE_SERIE',
    'instance_id': 'ecoflow-bridge',
    'snapshot_interval': 60,
    'freshness_seconds': 180,
    'topic_prefix': 'ecoflow/delta3classic',
    'local_mqtt': {
        'host': getpass.getpass('Adresse du broker MQTT du HA cible : ').strip(),
        'port': 1883,
        'username': getpass.getpass('Utilisateur MQTT local : ').strip(),
        'password': getpass.getpass('Mot de passe MQTT local : '),
        'tls': False,
    },
}
if not config['email'] or not config['password'] or not all(config['local_mqtt'][k] for k in ['host', 'username', 'password']):
    raise SystemExit('Champ vide : aucun fichier créé.')
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as stream:
    json.dump(config, stream, indent=2)
    stream.write('\n')
print('Fichier privé créé en mode 600.')
PY
```

`credentials.example.json` montre le format avec des valeurs factices. L'ancien fichier contenant `access_key`/`secret_key` ne convient plus. Ne pas inclure le fichier privé dans Git ; protéger aussi les sauvegardes.

Si le broker cible impose TLS, modifier `local_mqtt.port` et mettre `local_mqtt.tls` à `true`. Une autorité privée peut être indiquée par `ca_file`, à monter également en lecture seule dans le conteneur. TLS EcoFlow reste toujours activé et vérifié.

Chaque collecteur doit avoir son propre `instance_id`. Ne pas lancer deux collecteurs pour cette batterie avec le même identifiant : leurs connexions pourraient s'évincer. Le `topic_prefix` doit rester celui du YAML fourni, ou être changé partout.

## 5. Tester en lecture seule puis démarrer le service

Un essai borné, qui ne publie rien sur le broker HA cible mais demande un snapshot EcoFlow :

```bash
docker compose build
docker compose run --rm ecoflow-mqtt \
  --config /run/secrets/ecoflow.json --observe --duration 90
```

Les logs doivent montrer `application_login_and_certificate_ok`, `application_mqtt_subscribed`, `read_snapshot_requested`, puis une observation `soc` et `charge_limit`.

`--passive` désactive les demandes snapshot : il ne reste alors que l'écoute spontanée, avec la limite de silence déjà observée. Ne pas utiliser ce mode pour le service normal.

Démarrer ensuite le collecteur permanent :

```bash
docker compose up -d
docker compose logs --tail=30 -f ecoflow-mqtt
```

Le conteneur redémarre avec Docker via `restart: unless-stopped`. L'hôte doit lui-même démarrer Docker au boot. Le processus relance les sessions cloud avec temporisation et récupère un nouveau certificat ; une authentification explicitement rejetée impose quinze minutes d'attente. Les erreurs ne déclenchent aucun redémarrage de la batterie ou de HA.

Les journaux Docker sont limités à **trois fichiers de 5 Mo**. Le heartbeat journalise la connexion cloud, le broker cible, la fraîcheur du SOC, le nombre de messages et les requêtes de lecture. Un processus vivant avec `soc_fresh=False` reste une anomalie de collecte : ce n'est pas un succès.

## 6. Installer les capteurs dans le HA cible

Fusionner `homeassistant.yaml` dans `configuration.yaml` du HA de la batterie :

- ajouter les éléments `mqtt.sensor` et `mqtt.binary_sensor` aux listes existantes ;
- ajouter le bloc `template` à la liste existante ;
- ne pas créer de deuxième clé racine `mqtt:` ou `template:` ;
- avec des `!include`, ajouter les éléments au bon fichier inclus, sans dupliquer sa clé racine.

Si l'ancien lecteur HTTP a été installé sur ce HA, retirer uniquement ses entrées `command_line` et son ancien capteur Template EcoFlow avant d'ajouter la version MQTT. Ne pas supprimer d'autres capteurs. Nettoyer/renommer son ancienne entité devenue orpheline si elle réserve `sensor.ecoflow_batterie`.

Le YAML utilise `default_entity_id` pour proposer des noms stables, conformément à la [documentation MQTT Sensor](https://www.home-assistant.io/integrations/sensor.mqtt/). Vérifier la configuration avec votre version HA ; si elle ne supporte pas cette option, retirer ces lignes puis attribuer les identifiants attendus dans l'interface.

Vérifier la configuration, puis redémarrer le HA cible comme indiqué dans la documentation MQTT. Dans **Outils de développement → États**, vérifier les identifiants du tableau, les valeurs et les attributs `received_at`. Résoudre un éventuel suffixe d'entité avant d'installer l'automatisation.

### Fraîcheur et connectivité

Chaque mesure porte son propre instant de réception. Un message contenant seulement une puissance **ne rafraîchit pas** le SOC ni le plafond de charge.

Les mesures sont publiées **sans RETAIN** et les capteurs utilisent `expire_after: 180`. HA évite ainsi de traiter une ancienne mesure retenue comme une lecture récente au redémarrage. Cette recommandation est explicitée dans la [documentation des capteurs MQTT](https://www.home-assistant.io/integrations/sensor.mqtt/).

Seule la disponibilité du collecteur est retenue, avec un Last Will `offline`. Une déconnexion ou un arrêt propre la met également à `offline`. Ce signal représente la chaîne de transport, pas le statut physique `/status` public de la batterie.

Les templates contrôlent aussi le timestamp du SOC et du plafond. `now()` les réévalue chaque minute. L'automatisation vérifie ces âges directement avant toute coupure anticipée, même si une transition d'affichage tarde. Le timestamp est celui de la réception locale ; il ne prouve pas à lui seul l'instant de mesure physique dans le cloud.

## 7. Remplacer l'automatisation de recharge

Le fichier `automations.yaml` contient **une automatisation complète**, qui remplace l'ancienne **Prise Aqara - Heures Creuses**. Ne pas conserver les deux en parallèle.

Deux méthodes :

1. Dans le fichier `automations.yaml`, remplacer l'ancien élément par l'élément livré, avec son `id` ; ne pas remplacer toutes les autres automatisations du fichier.
2. Dans l'éditeur YAML de l'automatisation HA, utiliser le fichier `automation-ui.yaml` : il contient le même contenu sans tiret de liste racine ni `id`.

Vérifier que `switch.aqara_smart_plug_eu_2` est bien la prise qui alimente la batterie sur **ce HA**. Adaptez-le à votre prise ; ce nom est un exemple.

Comportement :

- **01h55** : allumer la prise ; si des mesures fraîches montrent que la cible est déjà atteinte, la laisser/couper éteinte.
- **Pendant 01h55–04h20** : couper lorsque le SOC atteint **le plafond de charge configuré moins 0,2 point**, pendant deux minutes.
- **04h20** : couper la prise sans condition EcoFlow, même si MQTT est indisponible.
- Une mesure absente, invalide ou âgée de trois minutes ne permet pas une coupure anticipée.
- Un contrôle chaque minute rattrape la confirmation de batterie pleine après un rechargement de l'automatisation. La confirmation repart de zéro si le capteur devient indisponible.
- L'arrêt anticipé est limité au créneau de recharge, afin de préserver un usage manuel en dehors de celui-ci.

**Avec le plafond observé de 90 %, la cible d'arrêt est 89,8 %, pas 100 %.** La marge de 0,2 point évite de rester branché pour un SOC qui plafonne à 89,99 %. Pour une politique strictement à 100 %, il faut définir explicitement cette cible et tenir compte du plafond configuré de la batterie. Pour supprimer la marge, remplacer `0.2` dans les templates et l'automatisation, puis adapter la description.

La coupure horaire suppose que HA et la prise fonctionnent à 04h20. Si HA est arrêté à cet instant ou si la prise est indisponible, ce YAML seul ne garantit pas la coupure physique. Aucun réallumage automatique après un arrêt anticipé n'est prévu avant le prochain 01h55.

Vérifier la configuration et recharger les automatisations sur le HA cible. Contrôler la trace lors d'une exécution naturelle. Ne pas simuler un faux SOC sur le broker de production pour tester la coupure.

## 8. Carte de dashboard facultative

```yaml
type: entities
title: EcoFlow — recharge
entities:
  - sensor.ecoflow_batterie
  - sensor.ecoflow_plafond_charge
  - sensor.ecoflow_puissance_entree
  - sensor.ecoflow_puissance_sortie
  - sensor.ecoflow_puissance_secteur
  - binary_sensor.ecoflow_collecteur_connecte
  - binary_sensor.ecoflow_telemetrie_recente
  - binary_sensor.ecoflow_charge_cible_atteinte
  - switch.aqara_smart_plug_eu_2
```

## 9. Dépannage et vérification

| Symptôme | Vérification |
|---|---|
| Authentification refusée | Compte applicatif, mot de passe exact, serveur régional. Les AccessKey ne sont pas utilisées. |
| MQTT accepté, mais aucun SOC | Présence des requêtes snapshot, réponses `get_reply`, firmware/modèle et erreurs de décodage. |
| Cloud OK, capteurs HA absents | Broker cible, identifiants MQTT locaux, ACL du préfixe, YAML HA et noms d'entités. |
| Capteur MQTT indisponible | Âge propre à ce champ ; ne pas transformer en zéro. |
| Collecteur connecté mais télémétrie non récente | Le transport fonctionne, mais aucune nouvelle mesure SOC exploitable n'arrive. |
| État brut `-1` | État non reconnu : le capteur textuel reste `unknown`, sans déduction de charge. |
| `descriptor_hash_mismatch` | Descripteur absent/modifié ; remettre celui du livrable. |
| Arrêt anticipé non déclenché | Cible, fraîcheur SOC/plafond, deux minutes de confirmation, créneau horaire et état de la prise. |

Tests hors ligne, depuis le dossier livré :

```bash
python3 -m venv .venv-tests
.venv-tests/bin/python -m pip install -r requirements-test.txt
.venv-tests/bin/python -B -m unittest -v test_ecoflow_battery.py
```

Ils couvrent les champs CMS de la Classic, zéro, messages partiels, cache périmé, état inconnu, interdiction de publication de modification et conditions de coupure. Le rendu YAML/Jinja testé ne remplace pas la validation de configuration HA sur l'installation cible. Le collecteur complet et la prise n'ont pas été déployés/testés sur cet autre HA.
