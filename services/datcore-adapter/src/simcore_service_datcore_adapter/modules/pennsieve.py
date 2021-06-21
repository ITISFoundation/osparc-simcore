import logging

from fastapi.applications import FastAPI
from pennsieve import Pennsieve

from ..core.settings import PennsieveSettings
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)


class PennsieveApi(BaseServiceClientApi):
    async def ping(self) -> bool:
        pennsieve = Pennsieve(api_token=None, api_secret=None)
        profile = pennsieve.profile
        ok = profile is not None
        return ok


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApi,
        api_baseurl=f"http://{settings.host}:{settings.port}",
        service_name="pennsieve.io",
    )
