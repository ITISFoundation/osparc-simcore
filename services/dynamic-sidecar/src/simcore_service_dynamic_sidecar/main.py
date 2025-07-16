"""Main application to be deployed in for example uvicorn."""

from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.application import create_app


def app_factory() -> FastAPI:
    """Factory function to create the FastAPI app instance.

    This is used by uvicorn or other ASGI servers to run the application.
    """
    return create_app()
