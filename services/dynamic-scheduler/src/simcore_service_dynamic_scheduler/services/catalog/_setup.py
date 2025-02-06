from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ._public_client import CatalogPublicClient
from ._thin_client import CatalogThinClient


async def lifespan_catalog(app: FastAPI) -> AsyncIterator[State]:
    thin_client = CatalogThinClient(app)
    thin_client.set_to_app_state(app)
    thin_client.attach_lifespan_to(app)

    public_client = CatalogPublicClient(app)
    public_client.set_to_app_state(app)

    yield {}

    CatalogPublicClient.pop_from_app_state(app)
    CatalogThinClient.pop_from_app_state(app)
