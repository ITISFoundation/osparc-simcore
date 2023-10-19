import json
import logging
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from httpx._types import URLTypes
from jsonschema import ValidationError
from pydantic import parse_file_as
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel

from .app_data import AppDataMixin

if os.environ.get("API_SERVER_DEV_HTTP_CALLS_LOGS_PATH"):
    from .http_calls_capture import get_captured
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

    def __init__(self, capture_file: Path, **async_clint_kwargs):
        super().__init__(**async_clint_kwargs)
        assert capture_file.name.endswith(
            ".json"
        ), "The capture file should be a json file"
        self._capture_file: Path = capture_file

    async def request(self, method: str, url: URLTypes, **kwargs):
        response: httpx.Response = await super().request(method, url, **kwargs)

        capture_name = f"{method} {url}"
        _logger.info("Capturing %s ... [might be slow]", capture_name)
        try:
            capture: HttpApiCallCaptureModel = get_captured(
                name=capture_name, response=response
            )
            if (
                not self._capture_file.is_file()
                or self._capture_file.read_text().strip() == ""
            ):
                self._capture_file.write_text("[]")
            serialized_captures: list[HttpApiCallCaptureModel] = parse_file_as(
                list[HttpApiCallCaptureModel], self._capture_file
            )
            serialized_captures.append(capture)
            self._capture_file.write_text(
                json.dumps(jsonable_encoder(serialized_captures), indent=1)
            )
        except (CaptureProcessingException, ValidationError, httpx.RequestError):
            _logger.exception(
                "Unexpected failure with %s",
                capture_name,
                exc_info=True,
                stack_info=True,
            )
        return response


# HELPERS -------------------------------------------------------------


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
    client: httpx.AsyncClient | _AsyncClientForDevelopmentOnly = httpx.AsyncClient(
        base_url=api_baseurl
    )
    with suppress(AttributeError):
        # NOTE that this is a general function with no guarantees as when is going to be used.
        # Here, 'AttributeError' might be raied when app.state.settings is still not initialized
        if capture_path := app.state.settings.API_SERVER_DEV_HTTP_CALLS_LOGS_PATH:
            client = _AsyncClientForDevelopmentOnly(
                capture_file=capture_path, base_url=api_baseurl
            )

    # events
    def _create_instance() -> None:
        _logger.debug("Creating %s for %s", f"{type(client)=}", f"{api_baseurl=}")
        api_cls.create_once(
            app,
            client=client,
            service_name=service_name,
            **extra_fields,
        )

    async def _cleanup_instance() -> None:
        api_obj: BaseServiceClientApi | None = api_cls.pop_instance(app)
        if api_obj:
            await api_obj.client.aclose()

    app.add_event_handler("startup", _create_instance)
    app.add_event_handler("shutdown", _cleanup_instance)
