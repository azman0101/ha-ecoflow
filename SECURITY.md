# Politique de sécurité

## Signaler une vulnérabilité

Merci de **ne pas ouvrir d'issue publique** pour une faille de sécurité. Utilisez le signalement privé GitHub : onglet **Security → Report a vulnerability** du dépôt.

N'incluez jamais de mot de passe, jeton ou numéro de série réel dans un signalement ou dans des logs partagés.

## Périmètre et garanties

- Ce projet est entièrement généré par IA (voir le README) et n'a pas été audité par un tiers.
- Seule la dernière version publiée est maintenue.
- Les dépendances Python sont auditées par `pip-audit` et le code Python est analysé par Bandit dans la CI (`.github/workflows/security.yml`).
- Le collecteur ne publie vers le cloud EcoFlow que des requêtes de lecture (`property/get`) ; toute autre publication est refusée par le code.
- Les identifiants sont gardés en mémoire ou dans `/data/options.json` / `/tmp/ecoflow.json` (mode 600) à l'intérieur du conteneur ; ils ne sont jamais journalisés.
