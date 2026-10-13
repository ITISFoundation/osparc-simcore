# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import logging
from collections.abc import Iterable
from contextlib import suppress

import aiohttp.test_utils
import docker
import pytest
import requests
import requests.exceptions
from docker.errors import APIError
from pydantic import HttpUrl, TypeAdapter
from tenacity import retry
from tenacity.after import after_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .helpers.host import get_localhost_ip
from .helpers.xdist import get_worker_id


@pytest.fixture(scope="session")
def httpbin_base_url(request: pytest.FixtureRequest) -> Iterable[HttpUrl]:
    """
    Implemented as a fixture since it cannot rely on full availability of https://httpbin.org/ during testing
    """
    ip_address = get_localhost_ip()
    port = aiohttp.test_utils.unused_port()
    base_url = f"http://{ip_address}:{port}"

    client = docker.from_env()
    # NOTE: the name must be unique per xdist worker, otherwise concurrent workers
    # running this session fixture would race on creating the same container (409)
    container_name = f"httpbin-fixture-{get_worker_id(request)}"
    try:
        container = client.containers.run(
            image="mccutchen/go-httpbin:2.25.0",
            ports={"8080": port},  # go-httpbin default listen port
            name=container_name,
            detach=True,
        )

        @retry(
            wait=wait_fixed(1),
            retry=retry_if_exception_type(requests.exceptions.RequestException),
            stop=stop_after_delay(15),
            after=after_log(logging.getLogger(), logging.DEBUG),
        )
        def _wait_until_httpbin_is_responsive():
            r = requests.get(f"{base_url}/get", timeout=2)
            r.raise_for_status()

        _wait_until_httpbin_is_responsive()

        yield TypeAdapter(HttpUrl).validate_python(base_url)

    finally:
        with suppress(APIError):
            container = client.containers.get(container_name)
            container.remove(force=True)
