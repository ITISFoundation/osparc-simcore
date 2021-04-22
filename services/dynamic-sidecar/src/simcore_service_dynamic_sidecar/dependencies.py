from fastapi import Request

from .settings import DynamicSidecarSettings
from .shared_store import SharedStore


def get_settings(request: Request) -> DynamicSidecarSettings:
    return request.app.state.settings  # type: ignore


def get_shared_store(request: Request) -> SharedStore:
    return request.app.state.shared_store  # type: ignore
