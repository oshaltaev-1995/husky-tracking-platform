from fastapi import APIRouter

from app.api.routes.demo_dataset import router as demo_dataset_router
from app.api.routes.dogs import router as dogs_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(demo_dataset_router, tags=["demo-dataset"])
api_router.include_router(dogs_router, tags=["dogs"])
