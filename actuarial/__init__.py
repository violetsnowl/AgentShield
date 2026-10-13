"""AgentShield A0: independent research-only insurance calculations.

Not an insurer's pricing engine. Never computes verified economic losses from B refunds.
"""
from .claims import calculate_claim
from .estimate import calculate_quote

__all__ = ["calculate_claim", "calculate_quote"]
