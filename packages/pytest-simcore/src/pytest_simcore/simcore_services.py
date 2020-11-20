# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import logging
from typing import Dict, List

import aiohttp
import pytest
import tenacity
from yarl import URL

from .helpers.utils_docker import get_service_published_port

SERVICES_TO_SKIP = ["sidecar", "postgres", "redis", "rabbit"]
log = logging.getLogger(__name__)
SERVICE_HEALTHCHECK_ENTRYPOINT = {"director-v2": "/"}


@pytest.fixture(scope="module")
def services_endpoint(
    core_services: List[str], docker_stack: Dict, devel_environ: Dict
) -> Dict[str, URL]:
    services_endpoint = {}
    for service in core_services:
        assert f"simcore_{service}" in docker_stack["services"]
        if not service in SERVICES_TO_SKIP:
            endpoint = URL(
                f"http://127.0.0.1:{get_service_published_port(service, [8080, 8000])}"
            )
            services_endpoint[service] = endpoint
    return services_endpoint


@pytest.fixture(scope="function")
async def simcore_services(
    services_endpoint: Dict[str, URL], monkeypatch
) -> Dict[str, URL]:
    wait_tasks = [
        wait_till_service_responsive(
            f"{endpoint}{SERVICE_HEALTHCHECK_ENTRYPOINT.get(service, '/v0/')}"
        )
        for service, endpoint in services_endpoint.items()
    ]
    await asyncio.gather(*wait_tasks, return_exceptions=False)
    for service, endpoint in services_endpoint.items():
        monkeypatch.setenv(f"{service.upper().replace('-', '_')}_HOST", endpoint.host)
        monkeypatch.setenv(
            f"{service.upper().replace('-', '_')}_PORT", str(endpoint.port)
        )

    yield


# HELPERS --
@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_attempt(60),
    before_sleep=tenacity.before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_service_responsive(endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as resp:
            assert resp.status == 200
            data = await resp.json()
            # aiohttp based services are like this:
            assert "data" in data or ":-)" in data or ":-)" in data.get("msg")
            if "data" in data:
                assert "status" in data["data"]
                assert data["data"]["status"] == "SERVICE_RUNNING"
