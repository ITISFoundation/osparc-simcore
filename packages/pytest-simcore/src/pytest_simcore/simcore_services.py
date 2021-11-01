# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import logging
from typing import Dict, List

import aiohttp
import pytest
import tenacity
from _pytest.monkeypatch import MonkeyPatch
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

from .helpers.utils_docker import get_ip, get_service_published_port

log = logging.getLogger(__name__)

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
SERVICE_PUBLISHED_PORT = {}
SERVICE_HEALTHCHECK_ENTRYPOINT = {
    "director-v2": "/",
    "dask-scheduler": "/health",
}
AIOHTTP_BASED_SERVICE_PORT: int = 8080
FASTAPI_BASED_SERVICE_PORT: int = 8000
DASK_SCHEDULER_SERVICE_PORT: int = 8787


@pytest.fixture(scope="module")
def services_endpoint(
    core_services_selection: List[str], docker_stack: Dict, testing_environ_vars: Dict
) -> Dict[str, URL]:
    services_endpoint = {}

    stack_name = testing_environ_vars["SWARM_STACK_NAME"]
    for service in core_services_selection:
        assert f"{stack_name}_{service}" in docker_stack["services"]
        full_service_name = f"{stack_name}_{service}"
        if service not in SERVICES_TO_SKIP:
            endpoint = URL(
                f"http://{get_ip()}:{get_service_published_port(full_service_name, [AIOHTTP_BASED_SERVICE_PORT, FASTAPI_BASED_SERVICE_PORT, DASK_SCHEDULER_SERVICE_PORT])}"
            )
            services_endpoint[service] = endpoint
    return services_endpoint


@pytest.fixture(scope="module")
async def simcore_services(
    services_endpoint: Dict[str, URL], monkeypatch_module: MonkeyPatch
) -> None:

    # waits for all services to be responsive
    wait_tasks = [
        wait_till_service_responsive(
            URL(f"{endpoint}{SERVICE_HEALTHCHECK_ENTRYPOINT.get(service, '/v0/')}")
        )
        for service, endpoint in services_endpoint.items()
    ]
    await asyncio.gather(*wait_tasks, return_exceptions=False)

    # patches environment variables with host/port per service
    for service, endpoint in services_endpoint.items():
        env_prefix = service.upper().replace("-", "_")
        assert endpoint.host
        monkeypatch_module.setenv(f"{env_prefix}_HOST", endpoint.host)
        monkeypatch_module.setenv(f"{env_prefix}_PORT", str(endpoint.port))


# HELPERS --
@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_service_responsive(endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as resp:
            # NOTE: Health-check endpoint require only a
            # status code 200 (see e.g. services/web/server/docker/healthcheck.py)
            # regardless of the payload content
            assert resp.status == 200
