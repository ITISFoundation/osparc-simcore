"""Common dependency injection helpers for REST controllers.

This module provides factory functions for creating service instances
that are commonly used across multiple REST controllers in the login module.
"""

from aiohttp import web

from ....db.plugin import get_asyncpg_engine
from ..._confirmation_repository import ConfirmationRepository
from ..._confirmation_service import ConfirmationService
from ...settings import get_plugin_options


def get_confirmation_service(app: web.Application) -> ConfirmationService:
    """Get confirmation service instance from app.

    Creates a ConfirmationService with proper repository and options injection.
    Used across multiple REST controllers for confirmation operations.
    """
    engine = get_asyncpg_engine(app)
    repository = ConfirmationRepository(engine)
    options = get_plugin_options(app)
    return ConfirmationService(repository, options)
