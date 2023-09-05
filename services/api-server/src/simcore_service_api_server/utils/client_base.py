import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI
from httpx._types import URLTypes
from jsonschema import ValidationError

from .app_data import AppDataMixin
from .http_calls_capture import get_captured_as_json
from .http_calls_capture_processing import CaptureProcessingException

_logger = logging.getLogger(__name__)


@dataclass
class BaseServiceClientApi(AppDataMixin):
    """
    - wrapper around thin-client to simplify service's API calls
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - helpers to create a unique client instance per application and service
    """

    client: httpx.AsyncClient
    service_name: str
    health_check_path: str = "/"

    async def is_responsive(self) -> bool:
        try:
            resp = await self.client.get(self.health_check_path, timeout=1)
            resp.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as err:
            _logger.error("%s not responsive: %s", self.service_name, err)
            return False

    ping = is_responsive  # alias


class _AsyncClientForDevelopmentOnly(httpx.AsyncClient):
    """
    Adds captures mechanism
    """

    async def request(self, method: str, url: URLTypes, **kwargs):
        response: httpx.Response = await super().request(method, url, **kwargs)

        capture_name = f"{method} {url}"
        _logger.info("Capturing %s ... [might be slow]", capture_name)
        try:
            capture_json = get_captured_as_json(name=capture_name, response=response)
            _capture_logger.info("%s,", capture_json)
        except (CaptureProcessingException, ValidationError, httpx.RequestError):
            _capture_logger.exception(
                f"Unexpected failure with {capture_name=}",
                exc_info=True,
                stack_info=True,
            )
        return response


# HELPERS -------------------------------------------------------------

_capture_logger = logging.getLogger(f"{__name__}.capture")


def _setup_capture_logger_once(capture_path: Path) -> None:
    """NOTE: this is only to capture during development"""

    if not any(
        isinstance(hnd, logging.FileHandler) for hnd in _capture_logger.handlers
    ):
        file_handler = logging.FileHandler(filename=f"{capture_path}")
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter("%(message)s")
        file_handler.setFormatter(formatter)

        _capture_logger.addHandler(file_handler)
        _logger.info("Setup capture logger at %s", capture_path)


def setup_client_instance(
    app: FastAPI,
    api_cls: type[BaseServiceClientApi],
    api_baseurl,
    service_name: str,
    **extra_fields,
) -> None:
    """Helper to add init/cleanup of ServiceClientApi instances in the app lifespam"""

    assert issubclass(api_cls, BaseServiceClientApi)  # nosec

    # Http client class
    client_class: type = httpx.AsyncClient
    with suppress(AttributeError):
        # NOTE that this is a general function with no guarantees as when is going to be used.
        # Here, 'AttributeError' might be raied when app.state.settings is still not initialized
        if capture_path := app.state.settings.API_SERVER_DEV_HTTP_CALLS_LOGS_PATH:
            _setup_capture_logger_once(capture_path)
            client_class = _AsyncClientForDevelopmentOnly

    # events
    def _create_instance() -> None:
        _logger.debug("Creating %s for %s", f"{client_class=}", f"{api_baseurl=}")
        api_cls.create_once(
            app,
            client=client_class(base_url=api_baseurl),
            service_name=service_name,
            **extra_fields,
        )

    async def _cleanup_instance() -> None:
        api_obj: BaseServiceClientApi | None = api_cls.pop_instance(app)
        if api_obj:
            await api_obj.client.aclose()

    app.add_event_handler("startup", _create_instance)
    app.add_event_handler("shutdown", _cleanup_instance)
