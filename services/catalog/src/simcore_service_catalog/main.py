"""Main application to be deployed in for example uvicorn."""

from typing import Final

from simcore_service_catalog.core.application import create_app

assert create_app  # nosec
__all__: Final[tuple[str, ...]] = ("create_app",)
