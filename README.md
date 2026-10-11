# Dépôt de modules complémentaires Home Assistant — EcoFlow

Ce dépôt contient le module complémentaire Home Assistant pour connecter et intégrer les batteries EcoFlow (notamment la **DELTA 3 Classic**) en temps réel via MQTT.

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
