"""Continuous multi-aircraft trajectory conflict detection."""

from .continuous import detect_conflicts
from .models import Conflict, ConflictDetector, ConflictThresholds, TrajectoryPoint

__all__ = ["Conflict", "ConflictDetector", "ConflictThresholds", "TrajectoryPoint", "detect_conflicts"]
