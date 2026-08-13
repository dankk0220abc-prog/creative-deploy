"""Reconcile one immutable Zhipu Attempt from its existing measured usage facts."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from creativedeploy_api.core.config import Settings
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.session import create_database_session_factory
from creativedeploy_api.services.zhipu_invocations import ZhipuUsageReconciliationService


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invocation-id", required=True, type=uuid.UUID)
    parser.add_argument("--attempt-id", required=True, type=uuid.UUID)
    return parser.parse_args()


async def _run(invocation_id: uuid.UUID, attempt_id: uuid.UUID) -> None:
    settings = Settings.model_validate({})
    engine = create_database_engine(settings)
    session_factory = create_database_session_factory(engine)
    try:
        async with session_factory() as session:
            result = await ZhipuUsageReconciliationService(session).reconcile(
                invocation_id=invocation_id,
                attempt_id=attempt_id,
            )
        print(
            json.dumps(
                {
                    "invocation_id": str(result.invocation_id),
                    "attempt_id": str(result.attempt_id),
                    "reservation_before_minor_units": (result.reservation_before_minor_units),
                    "measured_cost_minor_units": result.measured_cost_minor_units,
                    "committed_after_minor_units": result.committed_after_minor_units,
                    "reserved_after_minor_units": result.reserved_after_minor_units,
                    "reservation_state": result.reservation_state,
                },
                sort_keys=True,
            )
        )
    finally:
        await engine.dispose()


def main() -> None:
    arguments = _arguments()
    asyncio.run(_run(arguments.invocation_id, arguments.attempt_id))


if __name__ == "__main__":
    main()
