from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ._public_client import DirectorV0PublicClient
from ._thin_client import DirectorV0ThinClient


@asynccontextmanager
async def lifespan_director_v0(app: FastAPI) -> AsyncIterator[None]:

    thin_client = DirectorV0ThinClient(app)
    thin_client.set_to_app_state(app)
    thin_client.attach_lifespan_to(app)

    public_client = DirectorV0PublicClient(app)
    public_client.set_to_app_state(app)

    yield

    DirectorV0PublicClient.pop_from_app_state(app)
    DirectorV0ThinClient.pop_from_app_state(app)
