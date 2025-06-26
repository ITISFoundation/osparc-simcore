import asyncio
import functools
import logging
import urllib.parse
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from pprint import pformat
from typing import Any, Final

import httpx
from common_library.json_serialization import json_dumps, json_loads
from fastapi import FastAPI, HTTPException
from fastapi_lifespan_manager import State
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import NonNegativeInt, TypeAdapter
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from servicelib.logging_utils import log_catch, log_context
from starlette import status
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

from ..core.settings import ApplicationSettings, DirectorSettings
from ..errors import DirectorUnresponsiveError

_logger = logging.getLogger(__name__)

_MINUTE: Final[NonNegativeInt] = 60


_SERVICE_RUNTIME_SETTINGS: Final[str] = "simcore.service.settings"
_ORG_LABELS_TO_SCHEMA_LABELS: Final[dict[str, str]] = {
    "org.label-schema.build-date": "build_date",
    "org.label-schema.vcs-ref": "vcs_ref",
    "org.label-schema.vcs-url": "vcs_url",
}

_CONTAINER_SPEC_ENTRY_NAME = "ContainerSpec".lower()
_RESOURCES_ENTRY_NAME = "Resources".lower()


def _validate_kind(entry_to_validate: dict[str, Any], kind_name: str):
    for element in (
        entry_to_validate.get("value", {})
        .get("Reservations", {})
        .get("GenericResources", [])
    ):
        if element.get("DiscreteResourceSpec", {}).get("Kind") == kind_name:
            return True
    return False


_director_startup_retry_policy: dict[str, Any] = {
    # Random service startup order in swarm.
    # wait_random prevents saturating other services while startup
    #
    "wait": wait_random(2, 5),
    "stop": stop_after_delay(2 * _MINUTE),
    "before_sleep": before_sleep_log(_logger, logging.WARNING),
    "reraise": True,
}


def _return_data_or_raise_error(
    request_func: Callable[..., Awaitable[httpx.Response]],
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
        zelf: "DirectorClient", path: str, *args, **kwargs
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


class DirectorClient:
    """
    - wrapper around thin-client to simplify director's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception

    SEE services/catalog/src/simcore_service_catalog/api/dependencies/director.py
    """

    def __init__(self, base_url: str, app: FastAPI):
        settings: ApplicationSettings = app.state.settings

        assert settings.CATALOG_CLIENT_REQUEST  # nosec
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=settings.CATALOG_CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
        )
        if settings.CATALOG_TRACING:
            setup_httpx_client_tracing(self.client)

        assert settings.CATALOG_DIRECTOR  # nosec
        self.vtag = settings.CATALOG_DIRECTOR.DIRECTOR_VTAG

        self.default_max_memory = settings.DIRECTOR_DEFAULT_MAX_MEMORY
        self.default_max_nano_cpus = settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS

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

    async def get_service_labels(
        self,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> dict[str, Any]:
        response = await self.get(
            f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}/labels"
        )
        assert isinstance(response, dict)  # nosec
        return response

    async def get_service_extras(
        self,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> ServiceExtras:
        # NOTE: SEE https://github.com/ITISFoundation/osparc-simcore/issues/7509

        # check physical node requirements
        # all nodes require "CPU"
        result: dict[str, Any] = {
            "node_requirements": {
                "CPU": self.default_max_nano_cpus / 1.0e09,
                "RAM": self.default_max_memory,
            }
        }

        labels = await self.get_service_labels(service_key, service_version)
        _logger.debug("Compiling service extras from labels %s", pformat(labels))

        if _SERVICE_RUNTIME_SETTINGS in labels:
            service_settings: list[dict[str, Any]] = json_loads(
                labels[_SERVICE_RUNTIME_SETTINGS]
            )
            for entry in service_settings:
                entry_name = entry.get("name", "").lower()
                entry_value = entry.get("value")
                invalid_with_msg = None

                if entry_name == _RESOURCES_ENTRY_NAME:
                    if entry_value and isinstance(entry_value, dict):
                        res_limit = entry_value.get("Limits", {})
                        res_reservation = entry_value.get("Reservations", {})
                        # CPU
                        result["node_requirements"]["CPU"] = (
                            float(res_limit.get("NanoCPUs", 0))
                            or float(res_reservation.get("NanoCPUs", 0))
                            or self.default_max_nano_cpus
                        ) / 1.0e09
                        # RAM
                        result["node_requirements"]["RAM"] = (
                            res_limit.get("MemoryBytes", 0)
                            or res_reservation.get("MemoryBytes", 0)
                            or self.default_max_memory
                        )
                    else:
                        invalid_with_msg = f"invalid type for resource [{entry_value}]"

                    # discrete resources (custom made ones) ---
                    # check if the service requires GPU support
                    if not invalid_with_msg and _validate_kind(entry, "VRAM"):

                        result["node_requirements"]["GPU"] = 1
                    if not invalid_with_msg and _validate_kind(entry, "MPI"):
                        result["node_requirements"]["MPI"] = 1

                elif entry_name == _CONTAINER_SPEC_ENTRY_NAME:
                    # NOTE: some minor validation
                    # expects {'name': 'ContainerSpec', 'type': 'ContainerSpec', 'value': {'Command': [...]}}
                    if (
                        entry_value
                        and isinstance(entry_value, dict)
                        and "Command" in entry_value
                    ):
                        result["container_spec"] = entry_value
                    else:
                        invalid_with_msg = f"invalid container_spec [{entry_value}]"

                if invalid_with_msg:
                    _logger.warning(
                        "%s entry [%s] encoded in settings labels of service image %s:%s",
                        invalid_with_msg,
                        entry,
                        service_key,
                        service_version,
                    )

        # get org labels
        if service_build_details := {
            sl: labels[dl]
            for dl, sl in _ORG_LABELS_TO_SCHEMA_LABELS.items()
            if dl in labels
        }:

            result.update({"service_build_details": service_build_details})

        return TypeAdapter(ServiceExtras).validate_python(result, strict=True)


async def director_lifespan(app: FastAPI) -> AsyncIterator[State]:
    client: DirectorClient | None = None
    settings = app.state.settings.CATALOG_DIRECTOR

    assert isinstance(settings, DirectorSettings)  # nosec

    with log_context(
        _logger, logging.DEBUG, "Setup director at %s", f"{settings.base_url=}"
    ):
        async for attempt in AsyncRetrying(**_director_startup_retry_policy):
            with attempt:
                client = DirectorClient(base_url=settings.base_url, app=app)
                if not await client.is_responsive():
                    with suppress(Exception):
                        await client.close()
                    raise DirectorUnresponsiveError

            _logger.info(
                "Connection to director-v0 succeeded [%s]",
                json_dumps(attempt.retry_state.retry_object.statistics),
            )

        # set when connected
        app.state.director_api = client

    try:
        yield {}
    finally:
        if client:
            with log_catch(_logger, reraise=False):
                await asyncio.wait_for(client.close(), timeout=10)
