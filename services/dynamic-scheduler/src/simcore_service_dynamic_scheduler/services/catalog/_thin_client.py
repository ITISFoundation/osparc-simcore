import urllib.parse

from fastapi import FastAPI, status
from httpx import Response
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import AttachLifespanMixin
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from yarl import URL

from ...core.settings import ApplicationSettings


class CatalogThinClient(SingletonInAppStateMixin, BaseThinClient, AttachLifespanMixin):
    app_state_name: str = "catalog_thin_client"

    def __init__(self, app: FastAPI) -> None:
        settings: ApplicationSettings = app.state.settings
        assert settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT  # nosec

        super().__init__(
            total_retry_interval=int(
                settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT
            ),
            extra_allowed_method_names={
                "attach_lifespan_to",
                "get_from_app_state",
                "pop_from_app_state",
                "set_to_app_state",
            },
            base_url=settings.DYNAMIC_SCHEDULER_CATALOG_SETTINGS.api_base_url,
            tracing_settings=settings.DYNAMIC_SCHEDULER_TRACING,
        )

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_services_labels(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> Response:
        return await self.client.get(
            f"/services/{urllib.parse.quote(service_key, safe='')}/{service_version}/labels"
        )

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_services_specifications(
        self, user_id: UserID, service_key: ServiceKey, service_version: ServiceVersion
    ) -> Response:
        request_url = URL(
            f"/services/{urllib.parse.quote(service_key, safe='')}/{service_version}/specifications",
        ).with_query(user_id=user_id)
        return await self.client.get(f"{request_url}")
