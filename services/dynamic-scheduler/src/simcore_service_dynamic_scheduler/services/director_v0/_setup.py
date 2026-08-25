from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ._public_client import DirectorV0PublicClient
from ._thin_client import DirectorV0ThinClient


async def _director_v0_lifespan(app: FastAPI) -> AsyncIterator[State]:
    thin_client = DirectorV0ThinClient(app)
    thin_client.set_to_app_state(app)
    await thin_client.setup_client()
    try:
        public_client = DirectorV0PublicClient(app)
        public_client.set_to_app_state(app)

        yield {}
    finally:
        DirectorV0PublicClient.pop_from_app_state(app)
        await thin_client.teardown_client()
        DirectorV0ThinClient.pop_from_app_state(app)


def configure_director_v0(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_director_v0_lifespan)
