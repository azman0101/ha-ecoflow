# Dépôt de modules complémentaires Home Assistant — EcoFlow

Ce dépôt contient le module complémentaire Home Assistant pour connecter et intégrer les batteries EcoFlow (notamment la **DELTA 3 Classic**) en temps réel via MQTT.

> [!IMPORTANT]
> **Ce dépôt est un dépôt de modules complémentaires (add-ons) Home Assistant, pas une intégration HACS.**
> Ne l'ajoutez pas dans HACS : celui-ci répondra « The repository does not seem to be a integration, but an add-on repository. HACS does not manage add-ons. »
> Utilisez la boutique de modules complémentaires de Home Assistant (voir ci-dessous). Elle n'existe que sous Home Assistant OS ou Supervised ; avec Home Assistant Container ou Core, utilisez le conteneur Docker décrit dans [`ecoflow-battery-reader/README.md`](ecoflow-battery-reader/README.md).

## Installation du module complémentaire

1. Dans Home Assistant, allez dans **Paramètres** > **Modules complémentaires** > **Boutique des modules complémentaires** (Add-on Store).
2. Cliquez sur les trois points en haut à droite > **Dépôts**.
3. Ajoutez l'URL de ce dépôt :
   ```text
   https://github.com/azman0101/ha-ecoflow
   ```
4. Cliquez sur **Ajouter**, puis fermez la boîte de dialogue et actualisez la page.
5. Le module **EcoFlow DELTA 3 Reader** apparaîtra dans la boutique. Cliquez dessus puis sur **Installer**.

## Configuration

Dans l'onglet **Configuration** du module complémentaire :
- renseignez vos identifiants EcoFlow (e-mail et mot de passe) et le numéro de série de votre batterie (`device_sn`) ;
- laissez `local_mqtt.host` **vide** : le module utilise automatiquement le broker Mosquitto détecté par Home Assistant, sans identifiants à saisir (renseignez `local_mqtt` seulement pour un autre broker) ;
- cliquez sur **Enregistrer** puis sur **Démarrer**.

## Entités : aucune configuration YAML

Le module annonce lui-même ses entités à Home Assistant par la **découverte MQTT** : un appareil **« EcoFlow DELTA 3 »** apparaît dans *Paramètres → Appareils et services → MQTT*, avec le niveau de batterie, les limites de charge, les puissances, l'état de charge et des capteurs de santé (collecteur connecté, télémétrie récente, charge cible atteinte). Il n'y a **rien à copier dans `configuration.yaml`**. Prérequis : l'intégration MQTT de Home Assistant connectée à ce broker, avec la découverte activée (réglage par défaut).

Détails, options et migration depuis la 1.0.x : [`ecoflow-battery-reader/README.md`](ecoflow-battery-reader/README.md).

## Recharge programmée (optionnel, indépendant du module)

Piloter une prise pour ne charger que pendant une plage horaire est un besoin à part, qui n'a pas besoin du module : c'est un **blueprint** générique (n'importe quel interrupteur, n'importe quel capteur binaire « cible atteinte »). Il fonctionne très bien avec le capteur *Charge cible atteinte* du module.

[![Importer le blueprint dans Home Assistant](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fazman0101%2Fha-ecoflow%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fazman0101%2Fscheduled_charge_window.yaml)

Ou, dans Home Assistant : *Paramètres → Automatisations → Blueprints → Importer un blueprint*, puis collez
`https://github.com/azman0101/ha-ecoflow/blob/main/blueprints/automation/azman0101/scheduled_charge_window.yaml`.
Vous choisissez ensuite la prise, le capteur, les heures de début et de fin dans l'interface.

## Tableau de bord Lovelace (optionnel)

Un modèle complet et personnalisable de tableau de bord est disponible dans le dossier [`dashboards/`](dashboards/) :
- Jauge et niveau de batterie en temps réel ;
- Affichage de la cible de recharge (%) et témoin d'arrêt anticipé ;
- Suivi de la prise connectée (contrôle, puissance, énergie, courant) ;
- Graphiques de comparaison de puissances et chronologie 48h des cycles de charge ;
- Journal d'événements (logbook) horodaté des arrêts/démarrages.

Consultez [`dashboards/README.md`](dashboards/README.md) pour les instructions simples d'importation dans Home Assistant.

## ⚠️ Transparence : code 100 % généré par IA


**L'intégralité de ce dépôt — code Python, Dockerfile, configuration du module, blueprint Home Assistant, tests, documentation et workflows GitHub Actions — a été générée par des assistants d'intelligence artificielle** (OpenAI Codex et Anthropic Claude). Aucune ligne n'a été écrite à la main.

Concrètement :

- le code **n'a pas fait l'objet d'un audit de sécurité professionnel** ; une relecture humaine n'est pas garantie ;
- il a été testé sur une seule installation (une DELTA 3 Classic) — voir `ecoflow-battery-reader/VALIDATION.md` ;
- des erreurs, hallucinations ou comportements inattendus sont possibles ;
- **relisez le code avant de lui confier vos identifiants EcoFlow**, et ne vous reposez pas sur le blueprint de recharge ni sur le module pour une protection critique (incendie, sécurité des biens ou des personnes) ;
- le statut de droit d'auteur des contenus générés par IA varie selon les juridictions.

Les contributions (issues, pull requests) sont les bienvenues, y compris celles assistées par IA, à condition d'être relues et testées par leur auteur.

## Avertissement

Ce projet est **indépendant et non affilié à EcoFlow**. « EcoFlow » et « DELTA » sont des marques de leurs propriétaires. Il utilise l'API *applicative* non documentée du cloud EcoFlow (celle de l'application mobile) avec **vos** identifiants : ce protocole peut changer sans préavis, et son usage peut contrevenir aux conditions d'utilisation d'EcoFlow. Le collecteur est conçu en lecture seule, mais vous l'utilisez à vos propres risques.

## Licence

Distribué sous licence **Apache 2.0** — voir [`LICENSE`](LICENSE). Le fichier `delta3_descriptor.bin` dérive du projet [tolwi/hassio-ecoflow-cloud](https://github.com/tolwi/hassio-ecoflow-cloud) (Apache 2.0) : voir [`THIRD_PARTY.md`](ecoflow-battery-reader/THIRD_PARTY.md).

## Sécurité et contributions

- Signaler une vulnérabilité : voir [`SECURITY.md`](SECURITY.md) (ne publiez jamais d'identifiants dans une issue).
- Cycle de vie : CI (lint, tests, analyse de sécurité), build/publication de l'image à chaque *release* et mises à jour Dependabot — voir [`.github/workflows/`](.github/workflows/) et [`RELEASING.md`](RELEASING.md).
