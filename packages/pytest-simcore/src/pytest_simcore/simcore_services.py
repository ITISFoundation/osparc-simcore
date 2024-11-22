# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
import logging
import warnings
from dataclasses import dataclass
from io import StringIO
from typing import Iterator

import aiohttp
import pytest
from aiohttp.client import ClientTimeout
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random
from yarl import URL

from .helpers.constants import MINUTE
from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.typing_env import EnvVarsDict

log = logging.getLogger(__name__)


_SERVICES_TO_SKIP = {
    "agent",  # global mode deploy (NO exposed ports, has http API)
    "dask-sidecar",  # global mode deploy (NO exposed ports, **NO** http API)
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "static-webserver",
    "traefik",
    "whoami",
}
# TODO: unify healthcheck policies see  https://github.com/ITISFoundation/osparc-simcore/pull/2281
SERVICE_PUBLISHED_PORT = {}
DEFAULT_SERVICE_HEALTHCHECK_ENTRYPOINT = "/v0/"
MAP_SERVICE_HEALTHCHECK_ENTRYPOINT = {
    "autoscaling": "/",
    "clusters-keeper": "/",
    "dask-scheduler": "/health",
    "datcore-adapter": "/v0/live",
    "director-v2": "/",
    "dynamic-schdlr": "/",
    "efs-guardian": "/",
    "invitations": "/",
    "payments": "/",
    "resource-usage-tracker": "/",
}
AIOHTTP_BASED_SERVICE_PORT: int = 8080
FASTAPI_BASED_SERVICE_PORT: int = 8000
DASK_SCHEDULER_SERVICE_PORT: int = 8787

_SERVICE_NAME_REPLACEMENTS: dict[str, str] = {
    "dynamic-scheduler": "dynamic-schdlr",
}

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
            async with aiohttp.ClientSession(
                timeout=_ONE_SEC_TIMEOUT
            ) as session, session.get(endpoint) as response:
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
                f"{baseurl}{MAP_SERVICE_HEALTHCHECK_ENTRYPOINT.get(service_name, DEFAULT_SERVICE_HEALTHCHECK_ENTRYPOINT)}"
            ),
        )
        return obj


@pytest.fixture(scope="module")
def services_endpoint(
    core_services_selection: list[str],
    docker_stack: dict,
    env_vars_for_docker_compose: EnvVarsDict,
) -> dict[str, URL]:
    services_endpoint = {}

    stack_name = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    for service in core_services_selection:
        service = _SERVICE_NAME_REPLACEMENTS.get(service, service)
        assert f"{stack_name}_{service}" in docker_stack["services"]
        full_service_name = f"{stack_name}_{service}"

        # TODO: unify healthcheck policies see  https://github.com/ITISFoundation/osparc-simcore/pull/2281
        # TODO: get health-check cmd from Dockerfile or docker-compose (e.g. postgres?)
        if service not in _SERVICES_TO_SKIP:
            target_ports = [
                AIOHTTP_BASED_SERVICE_PORT,
                FASTAPI_BASED_SERVICE_PORT,
                DASK_SCHEDULER_SERVICE_PORT,
            ]
            endpoint = URL(
                f"http://{get_localhost_ip()}:{get_service_published_port(full_service_name, target_ports)}"
            )
            services_endpoint[service] = endpoint
        else:
            print(f"Collecting service endpoints: '{service}' skipped")

    return services_endpoint


def _wait_for_services_ready(services_endpoint: dict[str, URL]) -> None:
    # Compose and log healthcheck url entpoints

    health_endpoints = [
        ServiceHealthcheckEndpoint.create(service_name, endpoint)
        for service_name, endpoint in services_endpoint.items()
    ]

    with StringIO() as buffer:
        print(
            "Composing health-check endpoints for relevant stack's services:",
            file=buffer,
        )
        for h in health_endpoints:
            print(f" - {h.name} -> {h.url}", file=buffer)
        log.info(buffer.getvalue())

    async def _check_all_services_are_healthy():
        await asyncio.gather(
            *[wait_till_service_healthy(h.name, h.url) for h in health_endpoints],
            return_exceptions=False,
        )

    # check ready
    asyncio.run(_check_all_services_are_healthy())


@pytest.fixture
def simcore_services_ready(
    services_endpoint: dict[str, URL], monkeypatch: pytest.MonkeyPatch
) -> None:
    _wait_for_services_ready(services_endpoint)
    # patches environment variables with right host/port per service
    for service, endpoint in services_endpoint.items():
        env_prefix = service.upper().replace("-", "_")

        assert endpoint.host
        monkeypatch.setenv(f"{env_prefix}_HOST", endpoint.host)
        monkeypatch.setenv(f"{env_prefix}_PORT", str(endpoint.port))


@pytest.fixture(scope="module")
def _monkeypatch_module(request: pytest.FixtureRequest) -> Iterator[pytest.MonkeyPatch]:
    # WARNING: Temporarily ONLY for simcore_services_ready_module
    assert request.scope == "module"

    warnings.warn(
        f"{__name__} is deprecated, we highly recommend to use pytest.monkeypatch at function-scope level."
        "Large scopes lead to complex problems during tests",
        DeprecationWarning,
        stacklevel=1,
    )
    # Some extras to overcome https://github.com/pytest-dev/pytest/issues/363
    # SEE https://github.com/pytest-dev/pytest/issues/363#issuecomment-289830794

    mpatch_module = pytest.MonkeyPatch()
    yield mpatch_module
    mpatch_module.undo()


@pytest.fixture(scope="module")
def simcore_services_ready_module(
    services_endpoint: dict[str, URL], _monkeypatch_module: pytest.MonkeyPatch
) -> None:
    warnings.warn(
        "This fixture uses deprecated monkeypatch_module fixture"
        "Please do NOT use it!",
        DeprecationWarning,
        stacklevel=1,
    )
    _wait_for_services_ready(services_endpoint)
    # patches environment variables with right host/port per service
    for service, endpoint in services_endpoint.items():
        env_prefix = service.upper().replace("-", "_")

        assert endpoint.host

        _monkeypatch_module.setenv(f"{env_prefix}_HOST", endpoint.host)
        _monkeypatch_module.setenv(f"{env_prefix}_PORT", str(endpoint.port))
