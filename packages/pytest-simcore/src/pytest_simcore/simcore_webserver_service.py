# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import aiohttp
import pytest
import tenacity
from servicelib.minio_utils import ServiceRetryPolicyUponInitialization
from yarl import URL

from .helpers.docker import get_service_published_port
from .helpers.typing_env import EnvVarsDict


@pytest.fixture(scope="module")
def webserver_endpoint(
    docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict
) -> URL:
    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_webserver" in docker_stack["services"]

    endpoint = f"127.0.0.1:{get_service_published_port('webserver', 8080)}"
    return URL(f"http://{endpoint}")


@pytest.fixture
async def webserver_service(webserver_endpoint: URL, docker_stack: dict) -> URL:
    await wait_till_webserver_responsive(webserver_endpoint)
    return webserver_endpoint


@tenacity.retry(**ServiceRetryPolicyUponInitialization().kwargs)
async def wait_till_webserver_responsive(webserver_endpoint: URL):
    async with aiohttp.ClientSession() as session, session.get(
        webserver_endpoint.with_path("/v0/")
    ) as resp:
        # NOTE: Health-check endpoint require only a
        # status code 200 (see e.g. services/web/server/docker/healthcheck.py)
        # regardless of the payload content
        assert resp.status == 200
