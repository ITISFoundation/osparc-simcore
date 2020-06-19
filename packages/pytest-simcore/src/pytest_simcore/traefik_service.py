# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict, Tuple

import aiohttp
import pytest
import tenacity
from yarl import URL

from servicelib.minio_utils import MinioRetryPolicyUponInitialization

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def traefik_endpoints(docker_stack: Dict, devel_environ: Dict) -> Tuple[URL, URL, URL]:
    """get the endpoint for the given simcore_service.
    NOTE: simcore_service defined as a parametrization
    """
    assert "simcore_traefik" in docker_stack["services"]
    traefik_api_endpoint = f"127.0.0.1:{get_service_published_port('traefik', 8080)}"
    webserver_endpoint = f"127.0.0.1:{get_service_published_port('traefik', 80)}"
    apiserver_endpoint = f"127.0.0.1:{get_service_published_port('traefik', 10081)}"
    return (URL(f"http://{traefik_api_endpoint}"), URL(f"http://{webserver_endpoint}"), URL(f"http://{apiserver_endpoint}"))


@pytest.fixture(scope="function")
async def traefik_service(
    loop, traefik_endpoints: Tuple[URL, URL, URL], docker_stack: Dict
) -> Tuple[URL, URL, URL]:
    traefik_api_endpoint, webserver_endpoint, apiserver_endpoint = traefik_endpoints
    await wait_till_traefik_responsive(traefik_api_endpoint)
    yield traefik_endpoints


# HELPERS --

# TODO: this can be used by ANY of the simcore services!
@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
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
