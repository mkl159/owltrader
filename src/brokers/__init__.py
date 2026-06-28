"""Connecteurs broker (pattern Strategy) : exécuter des ordres via une API externe.

- SimulatedBroker : le moteur fictif interne (déjà utilisé par le mode autonome).
- AlpacaBroker : vrai compte de paper-trading Alpaca via API REST (clés gratuites).
"""

from .alpaca import AlpacaBroker, to_alpaca_symbol  # noqa: F401
from .base import Broker  # noqa: F401
from .ccxt_broker import CCXTBroker, to_ccxt_symbol  # noqa: F401
