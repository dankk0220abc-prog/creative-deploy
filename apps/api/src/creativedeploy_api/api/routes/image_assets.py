"""Owner-scoped immutable ImageAsset upload, metadata, and private preview routes."""

from collections.abc import AsyncIterator
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    Path,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from creativedeploy_api.api.dependencies import (
    ImageAssetServiceDependency,
    PrincipalDependency,
    RequestIdDependency,
)
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.schemas.image_assets import (
    CreateImageAssetRequest,
    ImageAssetListResponse,
    ImageAssetRead,
    ImageIntendedUsage,
    ImageRole,
    ImageSourceType,
)
from creativedeploy_api.services.image_assets import (
    ImageRangeNotSupportedError,
    ImageUploadTooLargeApplicationError,
    MultipartImageContractError,
    PrivateImageContent,
)

router = APIRouter(
    prefix="/paint-projects/{project_id}/images",
    tags=["paint-project-images"],
)

MULTIPART_FIELDS = frozenset(
    {
        "file",
        "role",
        "source_type",
        "intended_usage",
        "rights_attestation_confirmed",
        "rights_attestation_version",
    }
)
SCALAR_MULTIPART_FIELDS = MULTIPART_FIELDS - {"file", "intended_usage"}
MAX_MULTIPART_ENVELOPE_BYTES = 64 * 1024
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Missing or inaccessible resource."},
    409: {"model": ErrorResponse, "description": "Idempotency or workflow conflict."},
    413: {"model": ErrorResponse, "description": "Upload is too large."},
    422: {"model": ErrorResponse, "description": "Multipart or image validation failed."},
    500: {"model": ErrorResponse, "description": "Safe internal failure."},
    503: {"model": ErrorResponse, "description": "Database or private storage unavailable."},
}


async def _require_exact_multipart(request: Request) -> None:
    form = await request.form()
    keys = set(form.keys())
    if keys != MULTIPART_FIELDS:
        raise MultipartImageContractError
    if len(form.getlist("file")) != 1:
        raise MultipartImageContractError
    if any(len(form.getlist(field)) != 1 for field in SCALAR_MULTIPART_FIELDS):
        raise MultipartImageContractError


def _require_supported_request_size(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared_bytes = int(content_length)
    except ValueError as error:
        raise MultipartImageContractError from error
    maximum_bytes = request.app.state.settings.image_upload_max_bytes + MAX_MULTIPART_ENVELOPE_BYTES
    if declared_bytes < 1:
        raise MultipartImageContractError
    if declared_bytes > maximum_bytes:
        raise ImageUploadTooLargeApplicationError


def _private_stream(content: PrivateImageContent) -> AsyncIterator[bytes]:
    async def iterate() -> AsyncIterator[bytes]:
        try:
            while chunk := content.stream.read(64 * 1024):
                yield chunk
        finally:
            content.stream.close()

    return iterate()


def _content_disposition(filename: str) -> str:
    return f"inline; filename*=UTF-8''{quote(filename, safe='')}"


@router.post(
    "",
    response_model=ImageAssetRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ImageAssetRead}, **ERROR_RESPONSES},
)
async def upload_project_image(
    request: Request,
    response: Response,
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    project_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    file: Annotated[UploadFile, File()],
    role: Annotated[ImageRole, Form()],
    source_type: Annotated[ImageSourceType, Form()],
    intended_usage: Annotated[list[ImageIntendedUsage], Form()],
    rights_attestation_confirmed: Annotated[bool, Form()],
    rights_attestation_version: Annotated[int, Form()],
) -> ImageAssetRead:
    """Create or replay one immutable original image and rights declaration."""
    _require_supported_request_size(request)
    await _require_exact_multipart(request)
    payload = CreateImageAssetRequest.model_validate(
        {
            "role": role,
            "source_type": source_type,
            "intended_usage": intended_usage,
            "rights_attestation_confirmed": rights_attestation_confirmed,
            "rights_attestation_version": rights_attestation_version,
        }
    )
    result = await service.upload_image(
        project_id=project_id,
        payload=payload,
        upload=file,
        principal=principal,
        idempotency_key=idempotency_key,
        correlation_id=request_id,
    )
    if result.replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return result.image


@router.get(
    "",
    response_model=ImageAssetListResponse,
    responses=ERROR_RESPONSES,
)
async def list_project_images(
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> ImageAssetListResponse:
    """List current and retained image history for one owner-scoped project."""
    return await service.list_images(project_id=project_id, principal=principal)


@router.get(
    "/{image_asset_id}",
    response_model=ImageAssetRead,
    responses=ERROR_RESPONSES,
)
async def get_project_image(
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    image_asset_id: Annotated[UUID, Path()],
) -> ImageAssetRead:
    """Read private ImageAsset metadata without exposing storage internals."""
    return await service.get_image(
        project_id=project_id,
        image_asset_id=image_asset_id,
        principal=principal,
    )


@router.get(
    "/{image_asset_id}/content",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}},
        416: {"model": ErrorResponse, "description": "Range requests are unsupported."},
        **ERROR_RESPONSES,
    },
)
async def get_project_image_content(
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    image_asset_id: Annotated[UUID, Path()],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    """Stream one authorized private object with cache and sniffing protections."""
    if range_header is not None:
        raise ImageRangeNotSupportedError
    content = await service.open_image_content(
        project_id=project_id,
        image_asset_id=image_asset_id,
        principal=principal,
    )
    return StreamingResponse(
        _private_stream(content),
        media_type=content.content_type,
        headers={
            "Accept-Ranges": "none",
            "Cache-Control": "private, no-store, max-age=0",
            "Content-Disposition": _content_disposition(content.filename),
            "Content-Length": str(content.byte_size),
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
