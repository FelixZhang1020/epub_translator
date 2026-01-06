"""Translation prompt strategies.

This module provides strategy classes for different translation modes.
Each strategy encapsulates the prompt building logic for a specific mode.
"""

from .base import PromptStrategy
from .direct import DirectTranslationStrategy
from .author_aware import AuthorAwareStrategy
from .optimization import OptimizationStrategy
from .iterative import IterativeStrategy

__all__ = [
    "PromptStrategy",
    "DirectTranslationStrategy",
    "AuthorAwareStrategy",
    "OptimizationStrategy",
    "IterativeStrategy",
]
