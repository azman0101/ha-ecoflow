# Tableau de bord EcoFlow DELTA 3

Ce dossier contient le modèle officiel de tableau de bord Lovelace pour superviser la batterie EcoFlow DELTA 3 et son cycle de recharge piloté par prise connectée.

## Fonctionnalités

- **Jauge de batterie en direct** (niveau %, seuils d'alerte couleur).
- **Cible de recharge** (plafond de charge en %, détection d'arrêt anticipé).
- **Prise de charge connectée** (interrupteur ON/OFF, puissance W, énergie consommée kWh, courant A).
- **Télémétrie complète EcoFlow** (entrées secteur AC, entrées solaires PV, sorties, état de fonctionnement).
- **Graphiques comparatifs (12h)** : puissance mesurée par la prise physique vs puissance reçue par la batterie.
- **Chronologie des recharges (48h)** : barres d'états montrant les plages horaires exactes d'allumage et le moment d'atteinte de la cible.
- **Journal d'événements (48h)** : logbook détaillant les actions automatiques du blueprint et les bascules de prise.
- **Histogramme de consommation (7j)** : énergie injectée par heure en kWh.

---

## Installation dans Home Assistant

### Installation via l'interface graphique

1. Dans Home Assistant, allez dans **Paramètres** > **Tableaux de bord** > bouton **Ajouter un tableau de bord** (en bas à droite).
2. Choisissez **Nouveau tableau de bord à partir de zéro** :
   - **Titre** : `EcoFlow`
   - **Icône** : `mdi:battery-charging-100`
   - **URL** : `dashboard-ecoflow`
3. Ouvrez le nouveau tableau de bord dans votre barre latérale.
4. Cliquez sur les **trois petits points verticaux** (en haut à droite) > **Modifier le tableau de bord**.
5. Cliquez à nouveau sur les **trois petits points** > **Éditeur de configuration brute** (Raw configuration editor).
6. Ouvrez le fichier [`ecoflow_dashboard.yaml`](ecoflow_dashboard.yaml) et remplacez **chaque** nom en majuscules par vos identifiants, idéalement avec la fonction Rechercher / Remplacer de votre éditeur (`Ctrl+H`) :
   - `YOUR_PLUG_SWITCH` : l'interrupteur de votre prise (ex: `switch.prise_salon`)
   - `YOUR_PLUG_POWER` : son capteur de puissance (ex: `sensor.prise_salon_power`)
   - `YOUR_PLUG_ENERGY` : son capteur d'énergie (ex: `sensor.prise_salon_energy`)
   - `YOUR_PLUG_CURRENT` : son capteur de courant. S'il n'existe pas, supprimez **les 3 lignes** de l'entrée (`- entity: YOUR_PLUG_CURRENT`, `name:` et `icon:`) : en supprimer une seule laisse un YAML invalide.
   - `YOUR_AUTOMATION` : l'automatisation créée depuis le blueprint (par défaut `automation.scheduled_charge_window_with_early_stop`, d'après son nom)
7. Collez le résultat dans l'éditeur et cliquez sur **Enregistrer**.

Les entités `sensor.ecoflow_*` et `binary_sensor.ecoflow_*` sont créées automatiquement par le module (découverte MQTT) : ne les modifiez pas.
