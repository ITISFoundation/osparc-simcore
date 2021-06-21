import logging

from fastapi.applications import FastAPI
from pennsieve import Pennsieve

from ..core.settings import PennsieveSettings
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)


class PennsieveApiClient(BaseServiceClientApi):
    async def ping(self) -> bool:
        return await self.is_responsive()
        # pennsieve = Pennsieve(api_token=None, api_secret=None)
        # profile = pennsieve.profile
        # ok = profile is not None
        # return ok


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApiClient,
        api_baseurl=f"{settings.URL}",
        service_name="pennsieve.io",
        health_check_path="/health/",
    )
