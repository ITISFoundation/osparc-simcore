import logging
from datetime import timedelta
from typing import Final, NamedTuple

from fastapi import FastAPI, status
from httpx import AsyncClient
from pydantic import AnyUrl, TypeAdapter
from servicelib.logging_utils import log_context
from settings_library.node_ports import StorageAuthSettings

from ..modules.service_liveness import wait_for_service_liveness
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_LIVENESS_TIMEOUT: Final[timedelta] = timedelta(seconds=5)


class _AuthTuple(NamedTuple):
    username: str
    password: str


def _get_auth_or_none(storage_auth_settings: StorageAuthSettings) -> _AuthTuple | None:
    if storage_auth_settings.auth_required:
        assert storage_auth_settings.STORAGE_USERNAME  # nosec
        assert storage_auth_settings.STORAGE_PASSWORD  # nosec
        return _AuthTuple(
            storage_auth_settings.STORAGE_USERNAME,
            storage_auth_settings.STORAGE_PASSWORD.get_secret_value(),
        )
    return None


def _get_url(storage_auth_settings: StorageAuthSettings) -> str:
    url: AnyUrl = TypeAdapter(AnyUrl).validate_python(
        f"{storage_auth_settings.api_base_url}/"
    )
    return f"{url}"


async def _is_storage_responsive(storage_auth_settings: StorageAuthSettings) -> bool:
    url = _get_url(storage_auth_settings)
    auth = _get_auth_or_none(storage_auth_settings)

    with log_context(
        _logger,
        logging.DEBUG,
        msg=f"checking storage connection at {url=} {auth=}",
    ):
        async with AsyncClient(
            auth=auth, timeout=_LIVENESS_TIMEOUT.total_seconds()
        ) as session:
            result = await session.get(url)
            if result.status_code == status.HTTP_200_OK:
                _logger.debug("storage connection established")
                return True
            _logger.error("storage is not responding %s", result.text)
            return False


async def wait_for_storage_liveness(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings
    storage_auth_settings = settings.NODE_PORTS_STORAGE_AUTH

    if storage_auth_settings is None:
        msg = f"Wrong configuration, check {StorageAuthSettings.__name__} for details"
        raise ValueError(msg)

    await wait_for_service_liveness(
        _is_storage_responsive,
        service_name="Storage",
        endpoint=_get_url(storage_auth_settings),
        storage_auth_settings=storage_auth_settings,
    )
