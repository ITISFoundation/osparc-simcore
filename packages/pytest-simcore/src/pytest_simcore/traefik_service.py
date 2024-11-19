# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import asyncio

import aiohttp
import pytest
import tenacity
from servicelib.minio_utils import ServiceRetryPolicyUponInitialization
from yarl import URL

from .helpers.docker import get_service_published_port
from .helpers.typing_env import EnvVarsDict


@pytest.fixture(scope="module")
def traefik_endpoints(
    docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict
) -> tuple[URL, URL, URL]:
    """get the endpoint for the given simcore_service.
    NOTE: simcore_service defined as a parametrization
    """
    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_traefik" in docker_stack["services"]

    traefik_api_endpoint = f"127.0.0.1:{get_service_published_port('traefik', 8080)}"
    webserver_endpoint = f"127.0.0.1:{get_service_published_port('traefik', 80)}"
    apiserver_endpoint = f"127.0.0.1:{get_service_published_port('traefik', 10081)}"
    return (
        URL(f"http://{traefik_api_endpoint}"),
        URL(f"http://{webserver_endpoint}"),
        URL(f"http://{apiserver_endpoint}"),
    )


@pytest.fixture()
async def traefik_service(
    event_loop: asyncio.AbstractEventLoop,
    traefik_endpoints: tuple[URL, URL, URL],
    docker_stack: dict,
) -> tuple[URL, URL, URL]:
    traefik_api_endpoint, webserver_endpoint, apiserver_endpoint = traefik_endpoints
    await wait_till_traefik_responsive(traefik_api_endpoint)
    return traefik_endpoints


# TODO: this can be used by ANY of the simcore services!
@tenacity.retry(**ServiceRetryPolicyUponInitialization().kwargs)
async def wait_till_traefik_responsive(api_endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(api_endpoint.with_path("/api/http/routers")) as resp:
            assert resp.status == 200
            data = await resp.json()
            for proxied_service in data:
                assert "service" in proxied_service
                if "webserver" in proxied_service["service"]:
                    assert proxied_service["status"] == "enabled"
                elif "api-server" in proxied_service["service"]:
                    assert proxied_service["status"] == "enabled"
