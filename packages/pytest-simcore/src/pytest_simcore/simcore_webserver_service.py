# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import aiohttp
import pytest
import tenacity
from servicelib.minio_utils import MinioRetryPolicyUponInitialization
from yarl import URL

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def webserver_endpoint(docker_stack: Dict, devel_environ: Dict) -> URL:
    assert "simcore_webserver" in docker_stack["services"]
    endpoint = f"127.0.0.1:{get_service_published_port('webserver', '8080')}"

    return URL(f"http://{endpoint}")


@pytest.fixture(scope="function")
async def webserver_service(webserver_endpoint: URL, docker_stack: Dict) -> URL:
    await wait_till_webserver_responsive(webserver_endpoint)

    yield webserver_endpoint


# HELPERS --

# TODO: this can be used by ANY of the simcore services!
@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
async def wait_till_webserver_responsive(webserver_endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(webserver_endpoint.with_path("/v0/")) as resp:
            # NOTE: Health-check endpoint require only a
            # status code 200 (see e.g. services/web/server/docker/healthcheck.py)
            # regardless of the payload content
            assert resp.status == 200
