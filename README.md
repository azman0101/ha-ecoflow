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
- Renseignez vos identifiants EcoFlow (email et mot de passe).
- Vérifiez le numéro de série de votre batterie (`device_sn`).
- Renseignez vos identifiants de broker MQTT local (`core-mosquitto` par défaut, ou l'IP de votre HA).
- Cliquez sur **Enregistrer** puis sur **Démarrer**.

## Capteurs et automatisation

Voir les fichiers :
- `ecoflow-battery-reader/homeassistant.yaml` pour les entités capteurs MQTT à intégrer dans `configuration.yaml`.
- `ecoflow-battery-reader/automation-ui.yaml` pour l'automatisation de recharge de la prise Aqara en heures creuses.

## ⚠️ Transparence : code 100 % généré par IA

**L'intégralité de ce dépôt — code Python, Dockerfile, configuration du module, YAML Home Assistant, tests, documentation et workflows GitHub Actions — a été générée par des assistants d'intelligence artificielle** (OpenAI Codex et Anthropic Claude). Aucune ligne n'a été écrite à la main.

Concrètement :

- le code **n'a pas fait l'objet d'un audit de sécurité professionnel** ; une relecture humaine n'est pas garantie ;
- il a été testé sur une seule installation (une DELTA 3 Classic) — voir `ecoflow-battery-reader/VALIDATION.md` ;
- des erreurs, hallucinations ou comportements inattendus sont possibles ;
- **relisez le code avant de lui confier vos identifiants EcoFlow**, et ne vous reposez pas sur l'automatisation de recharge pour une protection critique (incendie, sécurité des biens ou des personnes) ;
- le statut de droit d'auteur des contenus générés par IA varie selon les juridictions.

Les contributions (issues, pull requests) sont les bienvenues, y compris celles assistées par IA, à condition d'être relues et testées par leur auteur.

## Avertissement

Ce projet est **indépendant et non affilié à EcoFlow**. « EcoFlow » et « DELTA » sont des marques de leurs propriétaires. Il utilise l'API *applicative* non documentée du cloud EcoFlow (celle de l'application mobile) avec **vos** identifiants : ce protocole peut changer sans préavis, et son usage peut contrevenir aux conditions d'utilisation d'EcoFlow. Le collecteur est conçu en lecture seule, mais vous l'utilisez à vos propres risques.

## Licence

Distribué sous licence **Apache 2.0** — voir [`LICENSE`](LICENSE). Le fichier `delta3_descriptor.bin` dérive du projet [tolwi/hassio-ecoflow-cloud](https://github.com/tolwi/hassio-ecoflow-cloud) (Apache 2.0) : voir [`THIRD_PARTY.md`](ecoflow-battery-reader/THIRD_PARTY.md).

## Sécurité et contributions

- Signaler une vulnérabilité : voir [`SECURITY.md`](SECURITY.md) (ne publiez jamais d'identifiants dans une issue).
- Cycle de vie : CI (lint, tests, analyse de sécurité), build/publication de l'image à chaque *release* et mises à jour Dependabot — voir [`.github/workflows/`](.github/workflows/) et [`RELEASING.md`](RELEASING.md).
