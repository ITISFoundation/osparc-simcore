# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import logging
import re
from contextlib import suppress
from typing import Iterable

import docker
import httpx
import pytest
import respx
from docker.errors import APIError
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from simcore_service_api_server.utils.logging import HttpApiCallCaptureModel
from tenacity import retry
from tenacity.after import after_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture(scope="module")
def httpbin_base_url() -> Iterable[str]:
    # yield "https://httpbin.org/" # sometimes is not available

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
            retry=retry_if_exception_type(httpx.HTTPError),
            stop=stop_after_delay(10),
            after=after_log(logging.getLogger(), logging.DEBUG),
        )
        def _wait_until_httpbin_is_responsive():
            r = httpx.get(f"{base_url}/get")
            r.raise_for_status()

        _wait_until_httpbin_is_responsive()

        yield base_url

    finally:
        with suppress(APIError):
            container = client.containers.get(container_name)
            container.remove(force=True)


async def test_capture_http_call(
    event_loop: asyncio.AbstractEventLoop, httpbin_base_url
):
    # CAPTURE
    async with httpx.AsyncClient() as client:

        response: httpx.Response = await client.get(f"{httpbin_base_url}/json")
        print(response)

        request: httpx.Request = response.request
        assert response.request

        captured = HttpApiCallCaptureModel.create_from_response(
            response, name="get_json"
        )

        print(captured.json(indent=1))

        # MOCK
        with respx.mock(
            base_url="http://test.it",
            assert_all_called=False,
            assert_all_mocked=True,  # IMPORTANT: KEEP always True!
        ) as respx_mock:

            respx_mock.request(
                method=captured.method,
                path=captured.path,
                name=captured.name,
            ).respond(
                status_code=captured.status_code,
                json=captured.response_body,
            )

            response: httpx.Response = await client.get("http://test.it/json")

            assert respx_mock[captured.name].called
            assert response.json() == captured.response_body
            assert response.status_code == captured.status_code


async def test_capture_http_dynamic_call(
    event_loop: asyncio.AbstractEventLoop, faker: Faker, httpbin_base_url: str
):

    # CAPTURE
    async with httpx.AsyncClient() as client:

        sample_uid = faker.uuid4()  # used during test sampling

        response: httpx.Response = await client.post(
            f"{httpbin_base_url}/anything/{sample_uid}",
            params={"n": 42},
            json={
                "resource_id": sample_uid,
                "static": "constant",
            },
        )
        print(response)

        request: httpx.Request = response.request
        assert response.request

        captured = HttpApiCallCaptureModel.create_from_response(
            response, name="get_anything"
        )

        assert captured.query == "n=42"

        # pattern with named-group
        pattern = rf"(?P<resouce_uid>{UUID_RE_BASE})"
        match = re.search(pattern, captured.path)
        assert match
        assert match.groupdict() == {"resouce_uid": sample_uid}

        # subs_json = re.sub(f"{resource_uid}", pattern, captured.json())
        # new_capture = HttpApiCallCaptureModel.parse_raw(subs_json)

        # MOCK
        with respx.mock(
            base_url="http://test.it",
            assert_all_called=True,
            assert_all_mocked=True,  # IMPORTANT: KEEP always True!
        ) as respx_mock:

            respx_mock.request(
                method=captured.method,
                path__regex=re.sub(
                    f"{sample_uid}", pattern, captured.path
                ),  # using REGEX
                name=captured.name,
            ).respond(
                status_code=captured.status_code,
                json=captured.response_body,
            )

            other_uid = faker.uuid4()

            response: httpx.Response = await client.post(
                f"http://test.it/anything/{other_uid}",
                params={"n": 42},
                json={
                    "resource_id": other_uid,
                    "static": "constant",
                },
            )

            assert respx_mock[captured.name].called
            assert response.json() == captured.response_body
            assert response.status_code == captured.status_code
