from fastapi import FastAPI

from ._public_client import DirectorV0PublicClient
from ._thin_client import DirectorV0ThinClient


def setup_director_v0(app: FastAPI) -> None:
    async def _on_startup() -> None:
        thin_client = DirectorV0ThinClient(app)
        thin_client.set_to_app_state(app)
        thin_client.attach_lifespan_to(app)

        public_client = DirectorV0PublicClient(app)
        public_client.set_to_app_state(app)

    async def _on_shutdown() -> None:
        DirectorV0PublicClient.pop_from_app_state(app)
        DirectorV0ThinClient.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
