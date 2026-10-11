# Publier une version

> **`config.yaml` référence l'image `ghcr.io/azman0101/ecoflow-delta3-reader`.** Le tag de la release doit pointer sur un commit qui contient déjà la nouvelle `version` : la fusion précède donc la publication de l'image. Créez la release **immédiatement** après la fusion ; pendant les quelques minutes du build, une mise à jour proposée par Home Assistant échoue (réessayer ensuite).

1. Mettre à jour `version` dans `ecoflow-battery-reader/config.yaml` et ajouter l'entrée dans `ecoflow-battery-reader/CHANGELOG.md`.
2. Fusionner sur `main` (la CI doit être verte).
3. Créer une *release* GitHub dont le tag est la `version` au format [SemVer](https://semver.org/lang/fr/), avec ou sans préfixe `v` (`1.0.1` ou `v1.0.1`). Les pré-versions (`1.1.0-rc.1`) sont acceptées et ne déplacent pas le tag `latest` ; les métadonnées de build (`+...`) sont refusées. **Créez la release depuis un commit de `main` qui contient déjà ce workflow** : GitHub utilise le fichier de workflow du commit tagué.
4. Le workflow `Release` vérifie que le tag (sans `v`) est du SemVer valide et égal à `version`, construit les images `amd64` et `aarch64`, les signe (Cosign) et publie le manifeste multi-arch sur `ghcr.io/azman0101/ecoflow-delta3-reader`.
5. **Première publication uniquement** : dans GitHub → *Packages* → `ecoflow-delta3-reader` → *Package settings*, passer la visibilité en **Public** (les paquets GHCR sont privés par défaut), sinon Home Assistant ne pourra pas télécharger l'image.
