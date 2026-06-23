"""Paper-trading : compte fictif autonome, frais de courtage, simulation, auto-tuning."""

from .fees import courtage  # noqa: F401
from .simulator import SimResult, simulate  # noqa: F401
