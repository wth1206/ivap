"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import analysis, chat, detection, health, knowledge

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(detection.router)
api_router.include_router(analysis.router)
api_router.include_router(knowledge.router)
api_router.include_router(chat.router)
