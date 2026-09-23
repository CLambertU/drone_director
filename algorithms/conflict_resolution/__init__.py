"""Explainable candidate-based conflict resolution with whole-fleet verification."""

from .models import (
    ConflictResolver, Resolution, ResolutionCandidate, ResolutionEnvironment, ResolutionWeights,
)
from .rules import resolve_conflict

__all__ = [
    "ConflictResolver", "Resolution", "ResolutionCandidate", "ResolutionEnvironment",
    "ResolutionWeights", "resolve_conflict",
]
