# Publier une version

> **État actuel : pas de `image:` dans `config.yaml`.** Home Assistant construit alors l'image localement depuis le `Dockerfile` (plus lent sur Raspberry Pi, mais sans dépendre d'un registre). Pour passer aux images pré-construites, publiez d'abord une release (étapes ci-dessous), rendez le paquet GHCR public, puis ajoutez `image: "ghcr.io/azman0101/ecoflow-delta3-reader"` dans `config.yaml`. Ajouter cette ligne **avant** que l'image existe fait échouer l'installation.

1. Mettre à jour `version` dans `ecoflow-battery-reader/config.yaml` et ajouter l'entrée dans `ecoflow-battery-reader/CHANGELOG.md`.
2. Fusionner sur `main` (la CI doit être verte).
3. Créer une *release* GitHub dont le tag est **identique** à `version` (ex. `1.0.1`, sans préfixe `v`).
4. Le workflow `Release` vérifie que tag = `version`, construit les images `amd64` et `aarch64`, les signe (Cosign) et publie le manifeste multi-arch sur `ghcr.io/azman0101/ecoflow-delta3-reader`.
5. **Première publication uniquement** : dans GitHub → *Packages* → `ecoflow-delta3-reader` → *Package settings*, passer la visibilité en **Public** (les paquets GHCR sont privés par défaut), sinon Home Assistant ne pourra pas télécharger l'image.

Home Assistant détecte une nouvelle version dès que `version` change sur `main` : créez la release juste après la fusion, car l'installation échoue tant que l'image n'est pas publiée (quelques minutes).
