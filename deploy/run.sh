#!/usr/bin/env bash
# Lance le bot avec redémarrage automatique en cas de crash — SANS sudo ni systemd.
# Pratique pour le garder actif tant qu'un terminal (ou tmux/screen) reste ouvert.
#   bash deploy/run.sh
set -uo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
echo "🦉 OwlTrader — supervision avec redémarrage auto. Ctrl+C pour arrêter."
while true; do
  python -m src.main
  code=$?
  echo "⚠️ Bot arrêté (code $code). Redémarrage dans 10s…"
  sleep 10
done
