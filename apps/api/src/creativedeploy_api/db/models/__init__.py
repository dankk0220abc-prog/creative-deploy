"""Explicit registration surface for approved Phase 1D-1B ORM models."""

from typing import Final

from creativedeploy_api.db.base import Base
from creativedeploy_api.db.models.command_idempotency_record import (
    CommandIdempotencyRecord,
)
from creativedeploy_api.db.models.paint_project import PaintProject
from creativedeploy_api.db.models.state_transition_event import StateTransitionEvent

REGISTERED_MODELS: Final[tuple[type[Base], ...]] = (
    PaintProject,
    StateTransitionEvent,
    CommandIdempotencyRecord,
)

__all__ = [
    "REGISTERED_MODELS",
    "CommandIdempotencyRecord",
    "PaintProject",
    "StateTransitionEvent",
]
