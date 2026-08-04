"""Create or confirm the deterministic, synthetic Phase 2E PaintPilot demo dataset."""

import asyncio
import io
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import UploadFile
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import Headers

from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.session import create_database_session_factory
from creativedeploy_api.repositories.identity import SqlAlchemyIdentityRepository
from creativedeploy_api.schemas.image_assets import (
    CreateImageAssetRequest,
    CreateReadinessReviewRequest,
    ImageRole,
)
from creativedeploy_api.schemas.paint_projects import CreatePaintProjectRequest
from creativedeploy_api.schemas.region_sets import (
    CreateRegionSetReviewRequest,
    RegionDraftInput,
    RegionKind,
    RegionVertexInput,
    SaveRegionSetRequest,
)
from creativedeploy_api.services.image_assets import ImageAssetService
from creativedeploy_api.services.paint_projects import PaintProjectService
from creativedeploy_api.services.region_sets import RegionSetService
from creativedeploy_api.storage.images import (
    ImageStoragePort,
    LocalFilesystemImageStorageAdapter,
)
from creativedeploy_api.storage.s3 import S3ImageStorageAdapter

DATASET_NAMESPACE = uuid.UUID("173eb1c5-8d88-4e8e-95e7-fc1c48fb9e9d")
PROJECT_TITLE = "PaintPilot synthetic public demo"
PROJECT_DESCRIPTION = (
    "Program-generated color-study images and human-authored polygons only. "
    "No customer or personal imagery."
)
IMAGE_SPECS: tuple[tuple[ImageRole, str, tuple[int, int, int]], ...] = (
    ("primary_front", "synthetic-primary-front.png", (209, 91, 67)),
    ("reference_back", "synthetic-reference-back.png", (59, 110, 180)),
    ("reference_angle", "synthetic-reference-angle.png", (66, 154, 119)),
    ("reference_detail", "synthetic-reference-detail.png", (190, 142, 72)),
)


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    project_id: uuid.UUID
    action: str


def _command_id(name: str) -> uuid.UUID:
    return uuid.uuid5(DATASET_NAMESPACE, name)


def _synthetic_image_bytes(color: tuple[int, int, int], *, role: str) -> bytes:
    """Build one program-authored PNG; no personal, licensed, or model-generated image is used."""
    image = Image.new("RGB", (1024, 768), (24, 31, 36))
    draw = ImageDraw.Draw(image)
    draw.rectangle((72, 72, 952, 696), fill=color)
    draw.rectangle((120, 120, 904, 648), outline=(242, 239, 231), width=10)
    draw.polygon(((210, 562), (512, 184), (814, 562)), fill=(29, 38, 43))
    draw.ellipse((420, 282, 604, 466), fill=(242, 239, 231))
    role_index = tuple(item[0] for item in IMAGE_SPECS).index(role)
    offset = 78 * role_index
    draw.rectangle((170 + offset, 142, 318 + offset, 194), fill=(242, 239, 231))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _regions() -> list[RegionDraftInput]:
    definitions: tuple[tuple[RegionKind, str, int, int, int], ...] = (
        ("paint", "Primary color field", 70_000, 80_000, 620_000),
        ("paint", "Accent plane", 405_000, 190_000, 500_000),
        ("exclude", "Reference boundary", 650_000, 590_000, 1_000_000),
    )
    result: list[RegionDraftInput] = []
    for z_index, (kind, label, x, y, opacity) in enumerate(definitions):
        result.append(
            RegionDraftInput(
                stable_region_key=_command_id(f"region:{label}"),
                kind=kind,
                label=label,
                z_index=z_index,
                opacity_ppm=opacity,
                notes="Human-authored synthetic demo annotation.",
                vertices=[
                    RegionVertexInput(x_ppm=x, y_ppm=y),
                    RegionVertexInput(x_ppm=x + 180_000, y_ppm=y),
                    RegionVertexInput(x_ppm=x + 180_000, y_ppm=y + 160_000),
                    RegionVertexInput(x_ppm=x, y_ppm=y + 160_000),
                ],
            )
        )
    return result


def _image_storage(settings: Settings) -> ImageStoragePort:
    if settings.image_storage_provider == "local_filesystem":
        return LocalFilesystemImageStorageAdapter(settings.require_local_image_storage())
    endpoint, region, bucket, access_key, secret_key, staging_root = (
        settings.require_s3_image_storage()
    )
    return S3ImageStorageAdapter(
        endpoint_url=endpoint,
        region=region,
        bucket=bucket,
        access_key_id=access_key,
        secret_access_key=secret_key,
        force_path_style=settings.s3_force_path_style,
        staging_root=staging_root,
        create_bucket=settings.s3_create_bucket,
    )


async def _ensure_demo_principal(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> PrincipalContext:
    subject, display_name, email = settings.require_demo_seed_identity()
    if settings.oidc_issuer is None:
        raise ValueError("The synthetic demo seed requires OIDC_ISSUER.")
    async with session_factory() as session, session.begin():
        user = await SqlAlchemyIdentityRepository(session).find_or_create_identity(
            issuer=settings.oidc_issuer,
            subject=subject,
            display_name=display_name,
            email=email,
            now=datetime.now(UTC),
        )
    return PrincipalContext(
        principal_id=str(user.id),
        principal_type=PrincipalType.HUMAN,
        display_name=user.display_name,
        authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
        user_id=user.id,
    )


async def seed_demo(settings: Settings) -> DemoSeedResult:
    """Use formal application services so every image and RegionSet invariant is exercised."""
    settings.require_demo_seed_identity()
    engine = create_database_engine(settings)
    session_factory = create_database_session_factory(engine)
    storage = _image_storage(settings)
    try:
        principal = await _ensure_demo_principal(session_factory, settings)
        async with session_factory() as session:
            projects = PaintProjectService(
                session,
                database_lock_timeout_ms=settings.database_lock_timeout_ms,
                database_statement_timeout_ms=settings.database_statement_timeout_ms,
            )
            existing = await projects.list_projects(principal=principal, limit=100, offset=0)
            matches = [
                project
                for project in existing.items
                if project.title == PROJECT_TITLE and project.description == PROJECT_DESCRIPTION
            ]
            if len(matches) > 1:
                raise RuntimeError("Multiple synthetic demo projects exist; run make demo-reset.")
            if matches:
                project = matches[0]
                images = ImageAssetService(session, storage, settings)
                regions = RegionSetService(session, storage, settings)
                image_set = await images.get_image_set(project_id=project.id, principal=principal)
                history = await regions.list_history(project_id=project.id, principal=principal)
                has_approved_snapshot = any(
                    item.effective_lifecycle == "approved" for item in history.items
                )
                if image_set.status != "ready" or not has_approved_snapshot:
                    raise RuntimeError("Synthetic demo data is incomplete; run make demo-reset.")
                return DemoSeedResult(project_id=project.id, action="confirmed")

            created = await projects.create_project(
                payload=CreatePaintProjectRequest(
                    title=PROJECT_TITLE,
                    description=PROJECT_DESCRIPTION,
                ),
                principal=principal,
                idempotency_key=_command_id("create-project"),
                correlation_id=_command_id("create-project-correlation"),
            )
            project = created.project
            images = ImageAssetService(session, storage, settings)
            for role, filename, color in IMAGE_SPECS:
                upload = UploadFile(
                    filename=filename,
                    file=io.BytesIO(_synthetic_image_bytes(color, role=role)),
                    headers=Headers({"content-type": "image/png"}),
                )
                try:
                    await images.upload_image(
                        project_id=project.id,
                        payload=CreateImageAssetRequest(
                            role=role,
                            source_type="user_provided_other",
                            intended_usage=[
                                "private_project",
                                "portfolio_demo",
                                "public_repository",
                            ],
                            rights_attestation_confirmed=True,
                            rights_attestation_version=1,
                        ),
                        upload=upload,
                        principal=principal,
                        idempotency_key=_command_id(f"upload:{role}"),
                        correlation_id=_command_id(f"upload:{role}:correlation"),
                    )
                finally:
                    await upload.close()
            await images.create_readiness_review(
                project_id=project.id,
                payload=CreateReadinessReviewRequest(verdict="ready"),
                principal=principal,
                idempotency_key=_command_id("image-set-ready"),
            )
            regions = RegionSetService(session, storage, settings)
            draft = await regions.save_draft(
                project_id=project.id,
                payload=SaveRegionSetRequest(
                    base_region_set_id=None,
                    base_version=None,
                    regions=_regions(),
                ),
                principal=principal,
                idempotency_key=_command_id("region-draft"),
            )
            submitted = await regions.submit(
                project_id=project.id,
                region_set_id=draft.id,
                principal=principal,
                idempotency_key=_command_id("region-submit"),
            )
            await regions.review(
                project_id=project.id,
                region_set_id=submitted.id,
                payload=CreateRegionSetReviewRequest(verdict="approved"),
                principal=principal,
                idempotency_key=_command_id("region-approved"),
            )
            return DemoSeedResult(project_id=project.id, action="created")
    finally:
        await engine.dispose()


def main() -> int:
    try:
        result = asyncio.run(seed_demo(Settings()))
    except Exception as error:
        print(f"DEMO_SEED_FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"DEMO_SEED_{result.action.upper()} project_id={result.project_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
