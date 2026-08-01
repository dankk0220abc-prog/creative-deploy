"""Provision isolated migrator/runtime roles with explicit least privilege."""

import asyncio
import os
import re
from collections.abc import Sequence

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from creativedeploy_api.core.config import Settings

ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} must be explicitly configured.")
    return value


def _role(name: str) -> str:
    value = _required(name)
    if ROLE_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a normalized PostgreSQL identifier.")
    return value


async def _ensure_role(
    connection: psycopg.AsyncConnection[tuple[object, ...]],
    *,
    role: str,
    password: str,
) -> None:
    exists = await connection.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = %s",
        (role,),
    )
    if await exists.fetchone() is None:
        await connection.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN PASSWORD {} "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
    else:
        await connection.execute(
            sql.SQL(
                "ALTER ROLE {} WITH LOGIN PASSWORD {} "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(role), sql.Literal(password))
        )


async def provision() -> int:
    settings = Settings.model_validate({})
    migrator = _role("DATABASE_MIGRATOR_ROLE")
    runtime = _role("DATABASE_RUNTIME_ROLE")
    if migrator == runtime:
        raise ValueError("Migrator and runtime roles must be different.")
    migrator_password = _required("DATABASE_MIGRATOR_PASSWORD")
    runtime_password = _required("DATABASE_RUNTIME_PASSWORD")
    sqlalchemy_url = make_url(settings.require_database_url().get_secret_value())
    database_name = sqlalchemy_url.database
    if database_name is None:
        raise ValueError("DATABASE_URL must select a database.")
    connection_url = sqlalchemy_url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    async with await psycopg.AsyncConnection.connect(connection_url, autocommit=True) as connection:
        await _ensure_role(
            connection,
            role=migrator,
            password=migrator_password,
        )
        await _ensure_role(
            connection,
            role=runtime,
            password=runtime_password,
        )
        for statement in (
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database_name)),
            sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
                sql.Identifier(database_name),
                sql.Identifier(migrator),
            ),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database_name),
                sql.Identifier(runtime),
            ),
            sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(migrator)),
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime)),
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
            ).format(sql.Identifier(runtime)),
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                sql.Identifier(runtime)
            ),
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(sql.Identifier(migrator), sql.Identifier(runtime)),
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO {}"
            ).format(sql.Identifier(migrator), sql.Identifier(runtime)),
        ):
            await connection.execute(statement)
    print(f"DATABASE_ROLES_PROVISIONED migrator={migrator} runtime={runtime} secrets_logged=0")
    return 0


def main(_argv: Sequence[str] | None = None) -> int:
    return asyncio.run(provision())


if __name__ == "__main__":
    raise SystemExit(main())
