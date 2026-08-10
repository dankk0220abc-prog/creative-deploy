"""Frozen Phase 3A fixture identities and state vocabularies."""

import uuid
from typing import Final

FIXTURE_PROVIDER_ID: Final = uuid.UUID("3a000000-0000-4000-8000-000000000001")
FIXTURE_TEXT_MODEL_ID: Final = uuid.UUID("3a000000-0000-4000-8000-000000000101")
FIXTURE_VISION_MODEL_ID: Final = uuid.UUID("3a000000-0000-4000-8000-000000000102")
FIXTURE_TEXT_CAPABILITY_ID: Final = uuid.UUID("3a000000-0000-4000-8000-000000001001")
FIXTURE_VISION_CAPABILITY_ID: Final = uuid.UUID("3a000000-0000-4000-8000-000000001002")
FIXTURE_STRUCTURED_CAPABILITY_ID: Final = uuid.UUID("3a000000-0000-4000-8000-000000001003")

FIXTURE_PROVIDER_KEY: Final = "fixture_local"
FIXTURE_TEXT_MODEL: Final = "fixture-text-v1"
FIXTURE_VISION_MODEL: Final = "fixture-vision-v1"
FIXTURE_CURRENCY: Final = "FIXTURE_CREDITS"
PROJECTLESS_SCOPE_ID: Final = uuid.UUID(int=0)
CANONICALIZATION_VERSION: Final = "phase3a-v1"

INVOCATION_FAMILIES: Final = (
    "fixture_credential_validation",
    "fixture_model_catalog",
    "fixture_invocation",
    "paint_plan_generation",
)
INVOCATION_STATUSES: Final = (
    "pending",
    "admitted",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "outcome_unknown",
)
ATTEMPT_STATUSES: Final = (
    "created",
    "admitted",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "outcome_unknown",
)
RESERVATION_STATES: Final = (
    "reserved",
    "dispatch_committed",
    "settled",
    "released",
    "reconciliation_required",
)
CREDENTIAL_STATUSES: Final = ("active", "revoked", "replaced")
