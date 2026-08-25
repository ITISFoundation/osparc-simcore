from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ._public_client import CatalogPublicClient
from ._thin_client import CatalogThinClient


async def _catalog_lifespan(app: FastAPI) -> AsyncIterator[State]:
    thin_client = CatalogThinClient(app)
    thin_client.set_to_app_state(app)
    await thin_client.setup_client()
    try:
        public_client = CatalogPublicClient(app)
        public_client.set_to_app_state(app)

        yield {}
    finally:
        CatalogPublicClient.pop_from_app_state(app)
        await thin_client.teardown_client()
        CatalogThinClient.pop_from_app_state(app)


def configure_catalog(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_catalog_lifespan)
