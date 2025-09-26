"""Common dependency injection helpers for REST controllers.

This module provides factory functions for creating service instances
that are commonly used across multiple REST controllers in the login module.
"""

from aiohttp import web

from ..._application_keys import CONFIRMATION_SERVICE_APPKEY
from ..._confirmation_service import ConfirmationService


def get_confirmation_service(app: web.Application) -> ConfirmationService:
    """Get confirmation service instance from app.
    Used across multiple REST controllers for confirmation operations.
    """
    return app[CONFIRMATION_SERVICE_APPKEY]
