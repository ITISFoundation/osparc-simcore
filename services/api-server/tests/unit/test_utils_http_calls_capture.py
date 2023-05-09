# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import re

import httpx
import respx
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from pydantic import HttpUrl
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel


async def test_capture_http_call(
    event_loop: asyncio.AbstractEventLoop, httpbin_base_url: HttpUrl
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
