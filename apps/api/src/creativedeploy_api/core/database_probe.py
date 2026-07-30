"""Safe database connectivity probe shared by local and CI Make gates."""

import asyncio

from creativedeploy_api.core.config import get_settings
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.services.database_health import DatabaseHealthService


async def _probe() -> None:
    settings = get_settings()
    engine = create_database_engine(settings)
    try:
        result = await DatabaseHealthService(
            engine,
            timeout_seconds=settings.database_health_timeout_seconds,
        ).check()
    finally:
        await engine.dispose()
    if result.status != "ok":
        raise SystemExit("PostgreSQL is unavailable for the resolved configuration.")
    print("PostgreSQL connection verified.")


if __name__ == "__main__":
    asyncio.run(_probe())
