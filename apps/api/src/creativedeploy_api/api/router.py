"""Top-level API router."""

from fastapi import APIRouter, Depends

from creativedeploy_api.api.dependencies import enforce_csrf
from creativedeploy_api.api.routes.ai_foundation import (
    project_policy_router as ai_project_policy_router,
)
from creativedeploy_api.api.routes.ai_foundation import router as ai_foundation_router
from creativedeploy_api.api.routes.arcana import router as arcana_router
from creativedeploy_api.api.routes.auth import router as auth_router
from creativedeploy_api.api.routes.health import router as health_router
from creativedeploy_api.api.routes.image_assets import router as image_assets_router
from creativedeploy_api.api.routes.image_sets import router as image_sets_router
from creativedeploy_api.api.routes.paint_plans import router as paint_plans_router
from creativedeploy_api.api.routes.paint_projects import (
    router as paint_projects_router,
)
from creativedeploy_api.api.routes.project_memberships import (
    router as project_memberships_router,
)
from creativedeploy_api.api.routes.region_sets import router as region_sets_router

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_csrf)])
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(paint_projects_router)
api_router.include_router(project_memberships_router)
api_router.include_router(image_assets_router)
api_router.include_router(image_sets_router)
api_router.include_router(region_sets_router)
api_router.include_router(paint_plans_router)
api_router.include_router(ai_foundation_router)
api_router.include_router(ai_project_policy_router)
api_router.include_router(arcana_router)
