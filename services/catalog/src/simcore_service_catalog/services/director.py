import asyncio
import functools
import logging
from typing import Any, Awaitable, Callable, Optional, Union

import httpx
from fastapi import FastAPI, HTTPException
from servicelib.json_serialization import json_dumps
from starlette import status
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

logger = logging.getLogger(__name__)

MINUTE = 60

director_startup_retry_policy = dict(
    # Random service startup order in swarm.
    # wait_random prevents saturating other services while startup
    #
    wait=wait_random(2, 5),
    stop=stop_after_delay(2 * MINUTE),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class UnresponsiveService(RuntimeError):
    pass


async def setup_director(app: FastAPI) -> None:
    if settings := app.state.settings.CATALOG_DIRECTOR:
        # init client-api
        logger.debug("Setup director at %s ...", f"{settings.base_url=}")
        client = DirectorApi(base_url=settings.base_url, app=app)

        # check that the director is accessible
        try:
            async for attempt in AsyncRetrying(**director_startup_retry_policy):
                with attempt:
                    if not await client.is_responsive():
                        raise UnresponsiveService("Director-v0 is not responsive")

                    logger.info(
                        "Connection to director-v0 succeded [%s]",
                        json_dumps(attempt.retry_state.retry_object.statistics),
                    )
        except UnresponsiveService:
            await client.close()
            raise

        app.state.director_api = client


async def close_director(app: FastAPI) -> None:
    client: Optional[DirectorApi]
    if client := app.state.director_api:
        await client.close()

    logger.debug("Director client closed successfully")


# DIRECTOR API CLASS ---------------------------------------------


def safe_request(
    request_func: Callable[..., Awaitable[httpx.Response]]
) -> Callable[..., Awaitable[Union[list[Any], dict[str, Any]]]]:
    """
    Creates a context for safe inter-process communication (IPC)
    """
    assert asyncio.iscoroutinefunction(request_func)

    def _unenvelope_or_raise_error(
        resp: httpx.Response,
    ) -> Union[list[Any], dict[str, Any]]:
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
            logger.error(
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
    ) -> Union[list[Any], dict[str, Any]]:
        normalized_path = path.lstrip("/")
        try:
            resp = await request_func(zelf, path=normalized_path, *args, **kwargs)
        except Exception as err:
            logger.exception(
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

    def __init__(self, base_url: str, app: FastAPI):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=app.state.settings.CATALOG_CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
        )
        self.vtag = app.state.settings.CATALOG_DIRECTOR.DIRECTOR_VTAG

    async def close(self):
        await self.client.aclose()

    # OPERATIONS
    # TODO: policy to retry if NetworkError/timeout?
    # TODO: add ping to healthcheck

    @safe_request
    async def get(self, path: str) -> httpx.Response:
        # temp solution: default timeout increased to 20"
        return await self.client.get(path, timeout=20.0)

    @safe_request
    async def put(self, path: str, body: dict) -> httpx.Response:
        return await self.client.put(path, json=body)

    async def is_responsive(self) -> bool:
        try:
            logger.debug("checking director-v0 is responsive")
            health_check_path: str = "/"
            result = await self.client.head(health_check_path, timeout=1.0)
            result.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException):
            return False
