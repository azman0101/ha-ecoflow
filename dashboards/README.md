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

### Méthode 1 : Via l'interface graphique (Recommandée)

1. Dans Home Assistant, allez dans **Paramètres** > **Tableaux de bord** > bouton **Ajouter un tableau de bord** (en bas à droite).
2. Choisissez **Nouveau tableau de bord à partir de zéro** :
   - **Titre** : `EcoFlow`
   - **Icône** : `mdi:battery-charging-100`
   - **URL** : `dashboard-ecoflow`
3. Ouvrez le nouveau tableau de bord dans votre barre latérale.
4. Cliquez sur les **trois petits points verticaux** (en haut à droite) > **Modifier le tableau de bord**.
5. Cliquez à nouveau sur les **trois petits points** > **Éditeur de configuration brute** (Raw configuration editor).
6. Ouvrez le fichier [`ecoflow_dashboard.yaml`](ecoflow_dashboard.yaml) :
   - Remplacez dans le texte :
     - `YOUR_PLUG_SWITCH` par l'interrupteur de votre prise (ex: `switch.prise_salon`)
     - `YOUR_PLUG_POWER` par le capteur de puissance de votre prise (ex: `sensor.prise_salon_power`)
     - `YOUR_PLUG_ENERGY` par le capteur d'énergie de votre prise (ex: `sensor.prise_salon_energy`)
     - `YOUR_PLUG_CURRENT` par le capteur de courant (ou supprimez la ligne si indisponible)
     - `YOUR_AUTOMATION` par l'identifiant de votre automatisation (ex: `automation.scheduled_charge_window_with_early_stop`)
7. Collez le résultat dans l'éditeur et cliquez sur **Enregistrer**.

### Personnalisation simple

Le fichier [`ecoflow_dashboard.yaml`](ecoflow_dashboard.yaml) utilise des noms explicites en majuscules faciles à remplacer avec la fonction Rechercher / Remplacer (`Ctrl+H` / `Cmd+F`) de votre éditeur :
- `YOUR_PLUG_SWITCH` : l'interrupteur de la prise (ex: `switch.prise_canape`)
- `YOUR_PLUG_POWER` : le capteur de puissance de la prise (ex: `sensor.prise_canape_power`)
- `YOUR_PLUG_ENERGY` : le capteur d'énergie de la prise (ex: `sensor.prise_canape_energy`)
- `YOUR_PLUG_CURRENT` : le capteur de courant de la prise (optionnel, supprimer si non disponible)
- `YOUR_AUTOMATION` : l'automatisation issue du blueprint (`automation.scheduled_charge_window_with_early_stop`)

