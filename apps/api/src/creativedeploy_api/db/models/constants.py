"""Frozen database contract constants for the initial PaintProject schema."""

from types import MappingProxyType
from typing import Final

MACHINE_TOKEN_PATTERN: Final = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
POSTGRESQL_MACHINE_TOKEN_PATTERN: Final = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
PAYLOAD_HASH_PATTERN: Final = r"^[0-9a-f]{64}$"

WORKFLOW_STATES: Final[tuple[str, ...]] = (
    "DRAFT",
    "IMAGE_UPLOADED",
    "IMAGE_REVIEW_REQUIRED",
    "IMAGE_VALIDATION_FAILED",
    "IMAGE_VALIDATED",
    "REGION_ANALYSIS_RUNNING",
    "REGION_REVIEW_REQUIRED",
    "REGIONS_CONFIRMED",
    "PLAN_GENERATION_RUNNING",
    "PLAN_REVIEW_REQUIRED",
    "PLAN_APPROVED",
    "COMPLETED",
    "BLOCKED_LOW_CONFIDENCE",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
    "ABANDONED",
)

TARGET_STYLE_CEL_SHADING: Final = "cel_shading"
PLANNING_MODE_DEMO: Final = "planning_only_demo"
IDEMPOTENCY_STATUS_IN_PROGRESS: Final = "in_progress"
IDEMPOTENCY_STATUS_COMPLETED: Final = "completed"

ACTOR_TYPES: Final[tuple[str, ...]] = ("user", "api", "worker", "system")
IDEMPOTENCY_STATUSES: Final[tuple[str, ...]] = (
    IDEMPOTENCY_STATUS_IN_PROGRESS,
    IDEMPOTENCY_STATUS_COMPLETED,
)

PHYSICAL_STRING_LENGTHS: Final = MappingProxyType(
    {
        "owner_principal_id": 128,
        "title": 80,
        "description": 500,
        "requested_target_style": 32,
        "planning_mode": 32,
        "status": 64,
        "from_state": 64,
        "to_state": 64,
        "event": 64,
        "actor_type": 32,
        "actor_principal_id": 128,
        "actor_display_name_snapshot": 200,
        "reason": 128,
        "scope_key": 512,
        "principal_id": 128,
        "command_type": 64,
        "payload_hash": 64,
        "execution_status": 32,
        "resource_type": 64,
    }
)
