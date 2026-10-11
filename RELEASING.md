# Publier une version

> **État actuel : pas de `image:` dans `config.yaml`.** Home Assistant construit alors l'image localement depuis le `Dockerfile` (plus lent sur Raspberry Pi, mais sans dépendre d'un registre). Pour passer aux images pré-construites, publiez d'abord une release (étapes ci-dessous), rendez le paquet GHCR public, puis ajoutez `image: "ghcr.io/azman0101/ecoflow-delta3-reader"` dans `config.yaml`. Ajouter cette ligne **avant** que l'image existe fait échouer l'installation.

1. Mettre à jour `version` dans `ecoflow-battery-reader/config.yaml` et ajouter l'entrée dans `ecoflow-battery-reader/CHANGELOG.md`.
2. Fusionner sur `main` (la CI doit être verte).
3. Créer une *release* GitHub dont le tag est la `version` au format [SemVer](https://semver.org/lang/fr/), avec ou sans préfixe `v` (`1.0.1` ou `v1.0.1`). Les pré-versions (`1.1.0-rc.1`) sont acceptées et ne déplacent pas le tag `latest` ; les métadonnées de build (`+...`) sont refusées. **Créez la release depuis un commit de `main` qui contient déjà ce workflow** : GitHub utilise le fichier de workflow du commit tagué.
4. Le workflow `Release` vérifie que le tag (sans `v`) est du SemVer valide et égal à `version`, construit les images `amd64` et `aarch64`, les signe (Cosign) et publie le manifeste multi-arch sur `ghcr.io/azman0101/ecoflow-delta3-reader`.
5. **Première publication uniquement** : dans GitHub → *Packages* → `ecoflow-delta3-reader` → *Package settings*, passer la visibilité en **Public** (les paquets GHCR sont privés par défaut), sinon Home Assistant ne pourra pas télécharger l'image.

Home Assistant détecte une nouvelle version dès que `version` change sur `main` : créez la release juste après la fusion, car l'installation échoue tant que l'image n'est pas publiée (quelques minutes).
