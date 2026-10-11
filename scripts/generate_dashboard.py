#!/usr/bin/env python3
"""Générateur de tableau de bord Lovelace personnalisé pour EcoFlow DELTA 3.

Ce script prend en entrée les identifiants de votre prise connectée et produit
un fichier YAML prêt à être importé dans Home Assistant.
"""
import argparse
from pathlib import Path
import sys

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / 'dashboards' / 'ecoflow_dashboard.yaml'


def main():
    parser = argparse.ArgumentParser(description='Génère un tableau de bord Lovelace EcoFlow personnalisé.')
    parser.add_argument('--switch', required=True, help='Interrupteur de la prise (ex: switch.ma_prise)')
    parser.add_argument('--power', required=True, help='Capteur de puissance en W (ex: sensor.ma_prise_power)')
    parser.add_argument('--energy', required=True, help='Capteur d\'énergie en kWh (ex: sensor.ma_prise_energy)')
    parser.add_argument('--current', default='', help='Capteur de courant en A (optionnel)')
    parser.add_argument('--automation', default='automation.scheduled_charge_window_with_early_stop',
                        help='Automatisation Blueprint de recharge')
    parser.add_argument('--output', '-o', default='', help='Fichier de sortie (par défaut stdout)')

    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print(f"[ERREUR] Modèle introuvable : {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    content = TEMPLATE_PATH.read_text(encoding='utf-8')

    # Sépare l'en-tête du corps YAML
    delimiter = '# ==============================================================================\n\n'
    if delimiter in content:
        header, body = content.split(delimiter, 1)
        body = body.replace('YOUR_PLUG_SWITCH', args.switch)
        body = body.replace('YOUR_PLUG_POWER', args.power)
        body = body.replace('YOUR_PLUG_ENERGY', args.energy)
        body = body.replace('YOUR_AUTOMATION', args.automation)

        if args.current:
            body = body.replace('YOUR_PLUG_CURRENT', args.current)
        else:
            lines = [line for line in body.splitlines() if 'YOUR_PLUG_CURRENT' not in line]
            body = '\n'.join(lines) + '\n'

        custom_header = f"""# ==============================================================================
# TABLEAU DE BORD ECOFLOW DELTA 3 (Généré)
# Prise : {args.switch} | Puissance : {args.power} | Énergie : {args.energy}
# ==============================================================================

"""
        content = custom_header + body
    else:
        content = content.replace('YOUR_PLUG_SWITCH', args.switch)
        content = content.replace('YOUR_PLUG_POWER', args.power)
        content = content.replace('YOUR_PLUG_ENERGY', args.energy)
        content = content.replace('YOUR_AUTOMATION', args.automation)


    if args.output:
        out_path = Path(args.output)
        out_path.write_text(content, encoding='utf-8')
        print(f"[SUCCÈS] Tableau de bord généré dans {out_path}")
    else:
        print(content)


if __name__ == '__main__':
    main()
