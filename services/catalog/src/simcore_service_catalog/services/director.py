import asyncio
import functools
import logging
import urllib.parse
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import httpx
from common_library.json_serialization import json_dumps
from fastapi import FastAPI, HTTPException
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from servicelib.logging_utils import log_context
from settings_library.tracing import TracingSettings
from starlette import status
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

from ..exceptions.errors import DirectorUnresponsiveError

_logger = logging.getLogger(__name__)

MINUTE = 60

_director_startup_retry_policy: dict[str, Any] = {
    # Random service startup order in swarm.
    # wait_random prevents saturating other services while startup
    #
    "wait": wait_random(2, 5),
    "stop": stop_after_delay(2 * MINUTE),
    "before_sleep": before_sleep_log(_logger, logging.WARNING),
    "reraise": True,
}


def _return_data_or_raise_error(
    request_func: Callable[..., Awaitable[httpx.Response]]
) -> Callable[..., Awaitable[list[Any] | dict[str, Any]]]:
    """
    Creates a context for safe inter-process communication (IPC)
    """
    assert asyncio.iscoroutinefunction(request_func)

    def _unenvelope_or_raise_error(
        resp: httpx.Response,
    ) -> list[Any] | dict[str, Any]:
        """
        Director responses are enveloped
        If successful response, we un-envelop it and return data as a dict
        If error, it raise an HTTPException
        """
        body = resp.json()

        assert "data" in body or "error" in body  # nosec
        data = body.get("data")
        error = body.get("error")

        if httpx.codes.is_server_error(resp.status_code):
            _logger.error(
                "director error %d [%s]: %s",
                resp.status_code,
                resp.reason_phrase,
                error,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        if httpx.codes.is_client_error(resp.status_code):
            msg = error or resp.reason_phrase
            raise HTTPException(resp.status_code, detail=msg)

        if isinstance(data, list):
            return data

        return data or {}

    @functools.wraps(request_func)
    async def request_wrapper(
        zelf: "DirectorApi", path: str, *args, **kwargs
    ) -> list[Any] | dict[str, Any]:
        normalized_path = path.lstrip("/")
        try:
            resp = await request_func(zelf, path=normalized_path, *args, **kwargs)
        except Exception as err:
            _logger.exception(
                "Failed request %s to %s%s",
                request_func.__name__,
                zelf.client.base_url,
                normalized_path,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return _unenvelope_or_raise_error(resp)

    return request_wrapper


class DirectorApi:
    """
    - wrapper around thin-client to simplify director's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception

    SEE services/catalog/src/simcore_service_catalog/api/dependencies/director.py
    """

    def __init__(
        self, base_url: str, app: FastAPI, tracing_settings: TracingSettings | None
    ):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=app.state.settings.CATALOG_CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
        )
        if tracing_settings:
            setup_httpx_client_tracing(self.client)
        self.vtag = app.state.settings.CATALOG_DIRECTOR.DIRECTOR_VTAG

    async def close(self):
        await self.client.aclose()

    #
    # Low level API
    #

    @_return_data_or_raise_error
    async def get(self, path: str) -> httpx.Response:
        # temp solution: default timeout increased to 20"
        return await self.client.get(path, timeout=20.0)

    #
    # High level API
    #

    async def is_responsive(self) -> bool:
        try:
            _logger.debug("checking director-v0 is responsive")
            health_check_path: str = "/"
            response = await self.client.head(health_check_path, timeout=1.0)
            response.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException):
            return False

    async def get_service(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceMetaDataPublished:
        data = await self.get(
            f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
        )
        # NOTE: the fact that it returns a list of one element is a defect of the director API
        assert isinstance(data, list)  # nosec
        assert len(data) == 1  # nosec
        return ServiceMetaDataPublished.model_validate(data[0])


async def setup_director(
    app: FastAPI, tracing_settings: TracingSettings | None
) -> None:
    if settings := app.state.settings.CATALOG_DIRECTOR:
        with log_context(
            _logger, logging.DEBUG, "Setup director at %s", f"{settings.base_url=}"
        ):
            async for attempt in AsyncRetrying(**_director_startup_retry_policy):
                client = DirectorApi(
                    base_url=settings.base_url,
                    app=app,
                    tracing_settings=tracing_settings,
                )
                with attempt:
                    client = DirectorApi(
                        base_url=settings.base_url,
                        app=app,
                        tracing_settings=tracing_settings,
                    )
                    if not await client.is_responsive():
                        with suppress(Exception):
                            await client.close()
                        raise DirectorUnresponsiveError

                _logger.info(
                    "Connection to director-v0 succeded [%s]",
                    json_dumps(attempt.retry_state.retry_object.statistics),
                )

            # set when connected
            app.state.director_api = client


async def close_director(app: FastAPI) -> None:
    client: DirectorApi | None
    if client := app.state.director_api:
        await client.close()

    _logger.debug("Director client closed successfully")
