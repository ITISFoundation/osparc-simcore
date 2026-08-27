from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ._public_client import CatalogPublicClient
from ._thin_client import CatalogThinClient


async def _catalog_thin_client_lifespan(app: FastAPI) -> AsyncIterator[State]:
    thin_client: CatalogThinClient | None = None
    try:
        thin_client = CatalogThinClient(app)
        thin_client.set_to_app_state(app)
        async with thin_client.lifespan():
            yield {}
    finally:
        if thin_client is not None and getattr(app.state, CatalogThinClient.app_state_name, None) is thin_client:
            CatalogThinClient.pop_from_app_state(app)


async def _catalog_public_client_lifespan(app: FastAPI) -> AsyncIterator[State]:
    public_client: CatalogPublicClient | None = None
    try:
        public_client = CatalogPublicClient(app)
        public_client.set_to_app_state(app)
        yield {}
    finally:
        if getattr(app.state, CatalogPublicClient.app_state_name, None) is public_client:
            CatalogPublicClient.pop_from_app_state(app)


def configure_catalog(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_catalog_thin_client_lifespan)
    app_lifespan.add(_catalog_public_client_lifespan)
