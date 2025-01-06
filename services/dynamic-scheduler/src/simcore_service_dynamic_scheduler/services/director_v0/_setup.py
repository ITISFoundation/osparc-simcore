from fastapi import FastAPI

from ...core.settings import ApplicationSettings
from ._public_client import DirectorV0PublicClient
from ._thin_client import DirectorV0ThinClient


def setup_director_v0(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    async def _on_startup() -> None:
        assert settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT  # nosec
        thin_client = DirectorV0ThinClient(
            total_retry_interval=int(
                settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT
            ),
            extra_allowed_method_names={
                "attach_lifespan_to",
                "get_from_app_state",
                "pop_from_app_state",
                "set_to_app_state",
            },
            base_url=settings.DYNAMIC_SCHEDULER_DIRECTOR_V0_SETTINGS.endpoint,
        )
        thin_client.set_to_app_state(app)
        thin_client.attach_lifespan_to(app)

        public_client = DirectorV0PublicClient(app)
        public_client.set_to_app_state(app)

    async def _on_shutdown() -> None:
        DirectorV0PublicClient.pop_from_app_state(app)
        DirectorV0ThinClient.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
