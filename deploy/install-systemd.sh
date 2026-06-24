#!/usr/bin/env bash
# Installe OwlTrader comme service systemd (démarre au boot, redémarre en cas de crash).
# Nécessite sudo. À lancer depuis la racine du projet : sudo bash deploy/install-systemd.sh
set -euo pipefail

UNIT=/etc/systemd/system/owltrader.service
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installation du service depuis $HERE"
sudo cp "$HERE/deploy/owltrader.service" "$UNIT"
sudo systemctl daemon-reload
sudo systemctl enable owltrader
sudo systemctl restart owltrader
echo "✅ Service installé. Commandes utiles :"
echo "   sudo systemctl status owltrader   # état"
echo "   journalctl -u owltrader -f        # logs en direct"
echo "   sudo systemctl restart owltrader  # redémarrer"
