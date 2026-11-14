"""Pilot code for "Do AI agents join strikes that will succeed without them?"

Implements the offline parts of proposal v4.1 (sections 3, 7 and 10): the
continuation task, the credit ledger, the game engine, role materials and the
leak test, output parsing, and cost logging. Nothing here calls a model
except strike.client, which needs an OpenRouter key.
"""

__version__ = "0.1.0"
