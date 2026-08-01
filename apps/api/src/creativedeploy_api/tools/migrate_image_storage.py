"""Copy local ImageAsset objects to S3 with checksum verification and resumability."""

import argparse
import asyncio
import hashlib
from collections.abc import Sequence

from sqlalchemy import select, update

from creativedeploy_api.core.config import Settings
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.models import ImageAsset
from creativedeploy_api.db.session import create_database_session_factory
from creativedeploy_api.storage.images import (
    ImageStorageError,
    LocalFilesystemImageStorageAdapter,
)
from creativedeploy_api.storage.s3 import S3ImageStorageAdapter


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy local private objects to configured S3 and update exact database "
            "references. Source files are never deleted."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform copy and database updates. Omit for a read-only dry run.",
    )
    parser.add_argument("--limit", type=int, default=None)
    result = parser.parse_args(argv)
    if result.limit is not None and result.limit < 1:
        parser.error("--limit must be positive")
    return result


async def migrate(*, execute: bool, limit: int | None) -> int:
    settings = Settings.model_validate({})
    endpoint, region, bucket, access_key, secret_key, staging_root = (
        settings.require_s3_image_storage()
    )
    source = LocalFilesystemImageStorageAdapter(
        settings.image_storage_root.expanduser().resolve(strict=False)
    )
    destination = S3ImageStorageAdapter(
        endpoint_url=endpoint,
        region=region,
        bucket=bucket,
        access_key_id=access_key,
        secret_access_key=secret_key,
        force_path_style=settings.s3_force_path_style,
        staging_root=staging_root,
        create_bucket=settings.s3_create_bucket and execute,
    )
    engine = create_database_engine(settings)
    session_factory = create_database_session_factory(engine)
    migrated = 0
    verified = 0
    try:
        async with session_factory() as session:
            statement = (
                select(ImageAsset)
                .where(ImageAsset.storage_provider == "local_filesystem")
                .order_by(ImageAsset.created_at, ImageAsset.id)
            )
            if limit is not None:
                statement = statement.limit(limit)
            assets = list((await session.execute(statement)).scalars().all())
        for asset in assets:
            stream = source.open_private(asset.storage_key)
            try:
                digest = hashlib.sha256()
                while chunk := stream.read(64 * 1024):
                    digest.update(chunk)
                if digest.hexdigest() != asset.sha256 or stream.tell() != asset.byte_size:
                    raise ImageStorageError(
                        f"ImageAsset {asset.id} source checksum or size did not match."
                    )
                verified += 1
                if not execute:
                    continue
                stream.seek(0)
                destination.copy_verified_object(
                    key=asset.storage_key,
                    source=stream,
                    byte_size=asset.byte_size,
                    sha256=asset.sha256,
                    content_type=asset.declared_content_type,
                )
            finally:
                stream.close()
            async with session_factory() as session, session.begin():
                updated = (
                    await session.execute(
                        update(ImageAsset)
                        .where(
                            ImageAsset.id == asset.id,
                            ImageAsset.storage_provider == "local_filesystem",
                            ImageAsset.storage_key == asset.storage_key,
                            ImageAsset.sha256 == asset.sha256,
                            ImageAsset.byte_size == asset.byte_size,
                        )
                        .values(storage_provider="s3")
                        .returning(ImageAsset.id)
                    )
                ).scalar_one_or_none()
                if updated is not None:
                    migrated += 1
        mode = "EXECUTE" if execute else "DRY_RUN"
        print(
            f"IMAGE_STORAGE_MIGRATION_{mode}_COMPLETE "
            f"verified={verified} updated={migrated} source_deleted=0"
        )
        return 0
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    return asyncio.run(migrate(execute=arguments.execute, limit=arguments.limit))


if __name__ == "__main__":
    raise SystemExit(main())
