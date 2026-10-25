"""
Source reliability tier system and rules.
Tier 1: Official Trade Registry / Government Gazettes
Tier 2: Verified International Reporting / Standard Trade Bulletins
Tier 3: Commercial Intelligence / Market Estimates
Tier 4: Unverified Rumors / Social Media / Anonymous Sources
"""

from __future__ import annotations

from src.core.schemas import ReliabilityTier, Document


class TierValidator:
    """
    Enforces judicial tier rules for source reliability.
    """

    @staticmethod
    def can_verify_event(tier: ReliabilityTier | int) -> bool:
        """
        Only Tier 1 or Tier 2 sources can substantiate event occurrence.
        """
        val = int(tier)
        return val in (1, 2)

    @staticmethod
    def can_support_claim(tier: ReliabilityTier | int) -> bool:
        """
        Tiers 1, 2, and 3 can support claims. Tier 4 cannot be used as sole proof.
        """
        return int(tier) <= 3

    @staticmethod
    def is_adversarial_or_rumor(tier: ReliabilityTier | int) -> bool:
        """
        Tier 4 sources must be treated with extreme caution and flagged.
        """
        return int(tier) >= 4

    @classmethod
    def filter_reliable_docs(cls, docs: list[Document]) -> list[Document]:
        """
        Filter out Tier 4 docs for verification workflows.
        """
        return [d for d in docs if cls.can_verify_event(d.reliability)]
