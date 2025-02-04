from fastapi import FastAPI

from ._public_client import CatalogPublicClient
from ._thin_client import CatalogThinClient


def setup_catalog(app: FastAPI) -> None:
    async def _on_startup() -> None:
        thin_client = CatalogThinClient(app)
        thin_client.set_to_app_state(app)
        thin_client.attach_lifespan_to(app)

        public_client = CatalogPublicClient(app)
        public_client.set_to_app_state(app)

    async def _on_shutdown() -> None:
        CatalogPublicClient.pop_from_app_state(app)
        CatalogThinClient.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
