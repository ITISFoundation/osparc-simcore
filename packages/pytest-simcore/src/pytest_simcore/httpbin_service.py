# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import logging
from contextlib import suppress
from typing import Iterable

import docker
import pytest
import requests
import requests.exceptions
from docker.errors import APIError
from pydantic import HttpUrl
from tenacity import retry
from tenacity.after import after_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture(scope="session")
def httpbin_base_url() -> Iterable[HttpUrl]:
    """Implemented since https://httpbin.org/ is not always available"""

    port = 80
    base_url = f"http://127.0.0.1:{port}"

    client = docker.from_env()
    container_name = "httpbin-fixture"
    try:
        client.containers.run(
            "kennethreitz/httpbin",
            ports={port: 80},
            name=container_name,
            detach=True,
        )

        @retry(
            wait=wait_fixed(1),
            retry=retry_if_exception_type(requests.exceptions.HTTPError),
            stop=stop_after_delay(10),
            after=after_log(logging.getLogger(), logging.DEBUG),
        )
        def _wait_until_httpbin_is_responsive():
            r = requests.get(f"{base_url}/get")
            r.raise_for_status()

        _wait_until_httpbin_is_responsive()

        yield parse_obj_as(HttpUrl, base_url)

    finally:
        with suppress(APIError):
            container = client.containers.get(container_name)
            container.remove(force=True)
