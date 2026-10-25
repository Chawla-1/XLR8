"""
Base Brain interface.
Defines the contract for agent decision-making.
Supports both deterministic RuleBrain (offline testing) and ClaudeBrain (production LLM).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseBrain(ABC):
    """
    Abstract Brain interface.
    Each agent delegates reasoning and structured generation to a Brain instance.
    """

    @abstractmethod
    def decide(
        self,
        role: str,
        task: str,
        context: dict[str, Any],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a reasoning step and return structured JSON.
        
        Args:
            role: Agent identity (e.g. "heimdall", "thor", "loki", "odin")
            task: Action description or instruction prompt
            context: Dynamic state (documents, claims, rulings, trade rows)
            system_prompt: Core operational rules and constraints for the role
            
        Returns:
            Dict containing structured response adhering to schemas
        """
        pass
