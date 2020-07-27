# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from typing import Dict, List

import aiohttp
import pytest
import tenacity
from yarl import URL

from servicelib.minio_utils import MinioRetryPolicyUponInitialization

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def services_endpoint(
    core_services: List[str], docker_stack: Dict, devel_environ: Dict
) -> Dict[str, URL]:
    services_endpoint = {}
    for service in core_services:
        assert f"simcore_{service}" in docker_stack["services"]
        if not service in ["postgres", "redis"]:
            endpoint = URL(
                f"http://127.0.0.1:{get_service_published_port(service, 8080)}"
            )
            services_endpoint[service] = endpoint
    return services_endpoint


@pytest.fixture(scope="function")
async def simcore_services(
    services_endpoint: Dict[str, URL], docker_stack: Dict
) -> Dict[str, URL]:
    wait_tasks = [
        wait_till_service_responsive(endpoint)
        for service, endpoint in services_endpoint.items()
    ]
    await asyncio.gather(*wait_tasks, return_exceptions=False)

    yield


# HELPERS --
@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
async def wait_till_service_responsive(endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint.with_path("/v0/")) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "data" in data
            assert "status" in data["data"]
            assert data["data"]["status"] == "SERVICE_RUNNING"
