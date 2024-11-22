# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import re
from pathlib import Path

import httpx
import jinja2
import respx
from faker import Faker
from models_library.basic_regex import UUID_RE_BASE
from pydantic import HttpUrl
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel


async def test_capture_http_call(
    event_loop: asyncio.AbstractEventLoop, httpbin_base_url: HttpUrl
):
    # CAPTURE
    async with httpx.AsyncClient() as client:
        response: httpx.Response = await client.get(f"{httpbin_base_url}json")
        print(response)

        _request: httpx.Request = response.request
        assert response.request

        captured = HttpApiCallCaptureModel.create_from_response(
            response, name="get_json", enhance_from_openapi_specs=False
        )

        print(captured.model_dump_json(indent=1))

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
            f"{httpbin_base_url}anything/{sample_uid}",
            params={"n": 42},
            json={
                "resource_id": sample_uid,
                "static": "constant",
            },
        )
        print(response)

        _request: httpx.Request = response.request
        assert response.request

        captured = HttpApiCallCaptureModel.create_from_response(
            response, name="get_anything", enhance_from_openapi_specs=False
        )

        assert captured.query == "n=42"

        # pattern with named-group
        pattern = rf"(?P<resouce_uid>{UUID_RE_BASE})"
        found = re.search(pattern, captured.path)
        assert found
        assert found.groupdict() == {"resouce_uid": sample_uid}

        # subs_json = re.sub(f"{resource_uid}", pattern, captured.json())
        # new_capture = HttpApiCallCaptureModel.model_validate_json(subs_json)

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

            response = await client.post(
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
        loader=jinja2.FileSystemLoader(project_tests_dir / "mocks"), autoescape=True
    )
    template = environment.get_template("delete_project_not_found.json")

    # loads parametrized capture
    # replace in response and solve
    capture = HttpApiCallCaptureModel.model_validate_json(template.render(context))
    print(capture.model_dump_json(indent=1))
    assert capture.path == url_path
