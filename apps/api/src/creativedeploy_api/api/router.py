"""Top-level API router."""

from fastapi import APIRouter

from creativedeploy_api.api.routes.health import router as health_router
from creativedeploy_api.api.routes.image_assets import router as image_assets_router
from creativedeploy_api.api.routes.paint_projects import (
    router as paint_projects_router,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(paint_projects_router)
api_router.include_router(image_assets_router)
