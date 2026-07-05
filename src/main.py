"""Point d'entrée du bot OwlTrader 🦉.

Lancement :
    python -m src.main
(nécessite TELEGRAM_BOT_TOKEN dans .env)
"""

from __future__ import annotations

import logging

from .bot.telegram_bot import build_application


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # yfinance crie "ERROR possibly delisted" quand la bourse est fermée (période 1d vide)
    # alors que le repli 5j fonctionne -> on coupe ce bruit pour garder des logs lisibles.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    app = build_application()
    logging.getLogger(__name__).info("🦉 OwlTrader démarré. En attente de messages…")
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
