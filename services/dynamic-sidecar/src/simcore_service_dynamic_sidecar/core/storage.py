import logging
from datetime import timedelta
from typing import Final

from fastapi import FastAPI, status
from httpx import AsyncClient
from servicelib.logging_utils import log_context

from ..modules.service_liveness import wait_for_service_liveness
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_LIVENESS_TIMEOUT: Final[timedelta] = timedelta(seconds=5)


async def _is_storage_responsive(url: str) -> bool:
    with log_context(
        _logger, logging.DEBUG, msg=f"checking storage connection at {url=}"
    ):
        async with AsyncClient(
            base_url=url, timeout=_LIVENESS_TIMEOUT.total_seconds()
        ) as session:
            result = await session.get("/")
            if result.status_code == status.HTTP_200_OK:
                _logger.debug("storage connection established")
                return True
            return False


async def wait_for_storage_liveness(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    storage_settings = app_settings.STORAGE_SETTINGS

    url = f"{storage_settings.api_base_url}/"
    await wait_for_service_liveness(
        _is_storage_responsive, service_name="Storage", endpoint=url, url=url
    )
