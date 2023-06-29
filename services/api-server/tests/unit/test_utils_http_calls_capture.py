# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import re
from pathlib import Path
from typing import Any

import httpx
import jinja2
import respx
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from openapi_core import create_spec, validate_request, validate_response
from pydantic import HttpUrl, parse_file_as
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
        found = re.search(pattern, captured.path)
        assert found
        assert found.groupdict() == {"resouce_uid": sample_uid}

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


def test_template_capture(project_tests_dir: Path, faker: Faker):
    # parse request and search parameters
    url_path = f"/v0/projects/{faker.uuid4()}"
    pattern = re.compile(rf"/projects/(?P<project_id>{UUID_RE_BASE})$")
    found = pattern.search(url_path)
    assert found
    context = found.groupdict()

    # get paramters from capture
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(project_tests_dir / "mocks")
    )
    template = environment.get_template("delete_project_not_found.json")

    # loads parametrized capture
    # replace in response and solve
    capture = HttpApiCallCaptureModel.parse_raw(template.render(context))
    print(capture.json(indent=1))
    assert capture.path == url_path


def test_mocks_captures_against_openapi(
    project_tests_dir: Path,
    catalog_service_openapi_specs: dict[str, Any],
    webserver_service_openapi_specs: dict[str, Any],
):
    captures = parse_file_as(
        list[HttpApiCallCaptureModel], project_tests_dir / "mocks" / "on_list_jobs.json"
    )

    openapi = {
        "catalog": create_spec(catalog_service_openapi_specs),
        "webserver": create_spec(webserver_service_openapi_specs),
    }

    for capture in captures:
        request = httpx.Request(
            method=capture.method,
            url=f"http://{capture.host}/{capture.path}",
            params=capture.query,
            json=capture.request_payload,
        )
        response = httpx.Response(
            status_code=capture.status_code, json=capture.response_body
        )
        validate_request(openapi[capture.host], request)
        validate_response(
            openapi[capture.host],
            request,
            response,
        )
