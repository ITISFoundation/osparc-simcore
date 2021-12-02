# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, List

import aiohttp
import pytest
from _pytest.monkeypatch import MonkeyPatch
from aiohttp.client import ClientTimeout
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random
from yarl import URL

from .helpers.constants import MINUTE
from .helpers.utils_docker import get_ip, get_service_published_port
from .helpers.utils_environs import EnvVarsDict

log = logging.getLogger(__name__)

# HELPERS --------------------------------------------------------------------------------


SERVICES_TO_SKIP = [
    "dask-sidecar",
    "migration",
    "postgres",
    "redis",
    "rabbit",
    "static-webserver",
    "whoami",
    "traefik",
]
# TODO: unify healthcheck policies see  https://github.com/ITISFoundation/osparc-simcore/pull/2281
SERVICE_PUBLISHED_PORT = {}
SERVICE_HEALTHCHECK_ENTRYPOINT = {
    "director-v2": "/",
    "dask-scheduler": "/health",
    "datcore-adapter": "/v0/live",
}
AIOHTTP_BASED_SERVICE_PORT: int = 8080
FASTAPI_BASED_SERVICE_PORT: int = 8000
DASK_SCHEDULER_SERVICE_PORT: int = 8787


_ONE_SEC_TIMEOUT = ClientTimeout(total=1)  # type: ignore


async def wait_till_service_healthy(service_name: str, endpoint: URL):

    log.info(
        "Connecting to %s",
        f"{service_name=} at {endpoint=}",
    )
    async for attempt in AsyncRetrying(
        # randomizing healthchecks sampling helps parallel execution
        wait=wait_random(1, 2),
        # sets the timeout for a service to become healthy
        stop=stop_after_delay(2 * MINUTE),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            async with aiohttp.ClientSession(timeout=_ONE_SEC_TIMEOUT) as session:
                async with session.get(endpoint) as response:
                    # NOTE: Health-check endpoint require only a status code 200
                    # (see e.g. services/web/server/docker/healthcheck.py)
                    # regardless of the payload content
                    assert (
                        response.status == 200
                    ), f"Connection to {service_name=} at {endpoint=} failed with {response=}"

            log.info(
                "Connection to %s succeeded [%s]",
                f"{service_name=} at {endpoint=}",
                json.dumps(attempt.retry_state.retry_object.statistics),
            )


@dataclass
class ServiceHealthcheckEndpoint:
    name: str
    url: URL

    @classmethod
    def create(cls, service_name: str, baseurl):
        # TODO: unify healthcheck policies see  https://github.com/ITISFoundation/osparc-simcore/pull/2281
        obj = cls(
            name=service_name,
            url=URL(
                f"{baseurl}{SERVICE_HEALTHCHECK_ENTRYPOINT.get(service_name, '/v0/')}"
            ),
        )
        return obj


# FIXTURES --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def services_endpoint(
    core_services_selection: List[str],
    docker_stack: Dict,
    testing_environ_vars: EnvVarsDict,
) -> Dict[str, URL]:
    services_endpoint = {}

    stack_name = testing_environ_vars["SWARM_STACK_NAME"]
    for service in core_services_selection:
        assert f"{stack_name}_{service}" in docker_stack["services"]
        full_service_name = f"{stack_name}_{service}"

        # TODO: unify healthcheck policies see  https://github.com/ITISFoundation/osparc-simcore/pull/2281
        # TODO: get health-check cmd from Dockerfile or docker-compose (e.g. postgres?)
        if service not in SERVICES_TO_SKIP:
            target_ports = [
                AIOHTTP_BASED_SERVICE_PORT,
                FASTAPI_BASED_SERVICE_PORT,
                DASK_SCHEDULER_SERVICE_PORT,
            ]
            endpoint = URL(
                f"http://{get_ip()}:{get_service_published_port(full_service_name, target_ports)}"
            )
            services_endpoint[service] = endpoint
        else:
            print(f"Collecting service endpoints: '{service}' skipped")

    return services_endpoint


@pytest.fixture(scope="module")
def simcore_services_ready(
    services_endpoint: Dict[str, URL], monkeypatch_module: MonkeyPatch
) -> None:
    """
    - Waits for services in `core_services_selection` to be healthy
    - Sets environment with these (host:port) endpoitns

    WARNING: not all services in the selection can be health-checked (see services_endpoint)
    """
    # Compose and log healthcheck url entpoints

    health_endpoints = [
        ServiceHealthcheckEndpoint.create(service_name, endpoint)
        for service_name, endpoint in services_endpoint.items()
    ]

    print("Composing health-check endpoints for relevant stack's services:")
    for h in health_endpoints:
        print(f" - {h.name} -> {h.url}")

    async def _check_all_services_are_healthy():
        await asyncio.gather(
            *[wait_till_service_healthy(h.name, h.url) for h in health_endpoints],
            return_exceptions=False,
        )

    # check ready
    asyncio.run(_check_all_services_are_healthy())

    # patches environment variables with right host/port per service
    for service, endpoint in services_endpoint.items():
        env_prefix = service.upper().replace("-", "_")

        assert endpoint.host

        monkeypatch_module.setenv(f"{env_prefix}_HOST", endpoint.host)
        monkeypatch_module.setenv(f"{env_prefix}_PORT", str(endpoint.port))
