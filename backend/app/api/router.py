from fastapi import APIRouter

from app.api.routes.daily_entry import router as daily_entry_router
from app.api.routes.daily_plans import router as daily_plans_router
from app.api.routes.demo_dataset import router as demo_dataset_router
from app.api.routes.dogs import router as dogs_router
from app.api.routes.health import router as health_router
from app.api.routes.kennel_map import router as kennel_map_router
from app.api.routes.team_builder import router as team_builder_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(demo_dataset_router, tags=["demo-dataset"])
api_router.include_router(dogs_router, tags=["dogs"])
api_router.include_router(kennel_map_router, tags=["kennel-map"])
api_router.include_router(daily_plans_router, tags=["daily-plans"])
api_router.include_router(team_builder_router, tags=["team-builder"])
api_router.include_router(daily_entry_router, tags=["daily-entry"])
