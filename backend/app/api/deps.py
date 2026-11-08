"""Shared FastAPI dependencies."""

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.storage import StorageService


def get_storage(settings: Settings = Depends(get_settings)) -> StorageService:
    return StorageService(settings.upload_dir)
