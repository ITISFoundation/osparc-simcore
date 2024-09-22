# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import logging
from contextlib import suppress
from typing import Iterable

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


@pytest.fixture(scope="session")
def httpbin_base_url() -> Iterable[HttpUrl]:
    """
    Implemented as a fixture since it cannot rely on full availability of https://httpbin.org/ during testing
    """
    ip_address = get_localhost_ip()
    port = aiohttp.test_utils.unused_port()
    base_url = f"http://{ip_address}:{port}"

    client = docker.from_env()
    container_name = "httpbin-fixture"
    try:
        container = client.containers.run(
            image="kennethreitz/httpbin",
            ports={80: port},
            name=container_name,
            detach=True,
        )
        print(container)

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
