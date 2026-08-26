from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ._public_client import DirectorV0PublicClient
from ._thin_client import DirectorV0ThinClient


async def _director_v0_thin_client_lifespan(app: FastAPI) -> AsyncIterator[State]:
    thin_client: DirectorV0ThinClient | None = None
    try:
        thin_client = DirectorV0ThinClient(app)
        thin_client.set_to_app_state(app)
        await thin_client.setup_client()
        yield {}
    finally:
        if thin_client is not None:
            try:
                await thin_client.teardown_client()
            finally:
                if getattr(app.state, DirectorV0ThinClient.app_state_name, None) is thin_client:
                    DirectorV0ThinClient.pop_from_app_state(app)


async def _director_v0_public_client_lifespan(app: FastAPI) -> AsyncIterator[State]:
    public_client: DirectorV0PublicClient | None = None
    try:
        public_client = DirectorV0PublicClient(app)
        public_client.set_to_app_state(app)
        yield {}
    finally:
        if getattr(app.state, DirectorV0PublicClient.app_state_name, None) is public_client:
            DirectorV0PublicClient.pop_from_app_state(app)


def configure_director_v0(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_director_v0_thin_client_lifespan)
    app_lifespan.add(_director_v0_public_client_lifespan)
