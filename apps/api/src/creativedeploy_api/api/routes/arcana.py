"""Authenticated Arcana Tarot product routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Path, status

from creativedeploy_api.api.dependencies import (
    ArcanaServiceDependency,
    PrincipalDependency,
    RequestIdDependency,
)
from creativedeploy_api.schemas.arcana import (
    TarotCatalogRead,
    TarotJournalUpdate,
    TarotLiveInterpretRequest,
    TarotReadingCreate,
    TarotReadingHistoryRead,
    TarotReadingRead,
    TarotSharePreviewRead,
)

router = APIRouter(prefix="/arcana", tags=["arcana"])


@router.get("/catalog", response_model=TarotCatalogRead)
async def get_catalog(service: ArcanaServiceDependency) -> TarotCatalogRead:
    return await service.catalog()


@router.post("/readings", response_model=TarotReadingRead, status_code=status.HTTP_201_CREATED)
async def start_reading(
    payload: TarotReadingCreate, service: ArcanaServiceDependency, principal: PrincipalDependency
) -> TarotReadingRead:
    return await service.start(payload, principal)


@router.get("/readings", response_model=TarotReadingHistoryRead)
async def list_readings(
    service: ArcanaServiceDependency, principal: PrincipalDependency
) -> TarotReadingHistoryRead:
    return await service.history(principal)


@router.get("/readings/{reading_id}", response_model=TarotReadingRead)
async def get_reading(
    reading_id: Annotated[UUID, Path()],
    service: ArcanaServiceDependency,
    principal: PrincipalDependency,
) -> TarotReadingRead:
    return await service.get(reading_id, principal)


@router.post("/readings/{reading_id}/draw", response_model=TarotReadingRead)
async def draw_reading(
    reading_id: Annotated[UUID, Path()],
    service: ArcanaServiceDependency,
    principal: PrincipalDependency,
) -> TarotReadingRead:
    return await service.draw(reading_id, principal)


@router.post("/readings/{reading_id}/interpret", response_model=TarotReadingRead)
async def interpret_reading(
    reading_id: Annotated[UUID, Path()],
    service: ArcanaServiceDependency,
    principal: PrincipalDependency,
) -> TarotReadingRead:
    return await service.interpret(reading_id, principal)


@router.post("/readings/{reading_id}/interpret-live", response_model=TarotReadingRead)
async def interpret_reading_live(
    reading_id: Annotated[UUID, Path()],
    payload: TarotLiveInterpretRequest,
    service: ArcanaServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> TarotReadingRead:
    return await service.interpret_live(
        reading_id,
        payload,
        principal,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


@router.put("/readings/{reading_id}/journal", response_model=TarotReadingRead)
async def save_journal(
    reading_id: Annotated[UUID, Path()],
    payload: TarotJournalUpdate,
    service: ArcanaServiceDependency,
    principal: PrincipalDependency,
) -> TarotReadingRead:
    return await service.save_journal(reading_id, payload, principal)


@router.get("/readings/{reading_id}/share-preview", response_model=TarotSharePreviewRead)
async def get_share_preview(
    reading_id: Annotated[UUID, Path()],
    service: ArcanaServiceDependency,
    principal: PrincipalDependency,
) -> TarotSharePreviewRead:
    return await service.share_preview(reading_id, principal)
