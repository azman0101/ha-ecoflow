# Provenance du schéma EcoFlow

`delta3_descriptor.bin` est le descripteur Protobuf extrait, sans exécuter le code amont, de :

https://github.com/tolwi/hassio-ecoflow-cloud/blob/main/custom_components/ecoflow_cloud/devices/internal/proto/ef_delta3_pb2.py

Projet : EcoFlow Cloud Integration for Home Assistant, auteurs/contributeurs du projet tolwi/hassio-ecoflow-cloud. Licence amont conservée dans `LICENSE.hassio-ecoflow-cloud`.

Source consultée le 11 octobre 2026.

- SHA-256 du fichier généré amont utilisé : `6685d42c8c66a72a28acf7d22657a9360a8ff5ce6bef82092ed2a81afbdcc14d`.
- SHA-256 du descripteur extrait : `c34e0f429a358dcafb94be7293fbd8d200f6700fbc929d7557affc7a2d83634a`.

Le schéma documente un protocole applicatif non officiel, susceptible d'évoluer. Le lecteur ne télécharge aucun code ou schéma au démarrage. Il décode les types de rapports connus et ignore les champs/rapports non reconnus. Les requêtes de lecture utilisent l'enveloppe « get all » décrite dans le fichier `devices/internal/delta3.py` du même projet.

Le reste du dépôt est distribué sous licence Apache 2.0 (voir `LICENSE` à la racine).
