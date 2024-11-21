# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
import re
import sys
from pathlib import Path
from typing import Any, TypeAlias

import httpx
import jsonref
import pytest
import respx
from pydantic import TypeAdapter
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from pytest_simcore.helpers.httpx_calls_capture_openapi import _determine_path
from pytest_simcore.helpers.httpx_calls_capture_parameters import (
    CapturedParameter,
    PathDescription,
)

try:
    from openapi_core import Spec, create_spec, validate_request, validate_response
    from openapi_core.contrib.starlette import (
        StarletteOpenAPIRequest,
        StarletteOpenAPIResponse,
    )

    OPENAPI_CORE_INSTALLED = True

except ImportError:
    Spec: TypeAlias = Any
    StarletteOpenAPIRequest = pytest.fail
    StarletteOpenAPIResponse = pytest.fail
    create_spec = pytest.fail
    validate_request = pytest.fail
    validate_response = pytest.fail

    OPENAPI_CORE_INSTALLED = False


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
_DUMMY_API_SERVER_OPENAPI = CURRENT_DIR / "dummy_api_server_openapi.json"


def _check_regex_pattern(pattern: str, match: str, non_match: str):
    assert re.match(pattern=pattern, string=match), f"{match=} did not match {pattern=}"
    assert not re.match(
        pattern=pattern, string=non_match
    ), f"{non_match=} matched {pattern=}"


@pytest.fixture
def openapi_specs(
    catalog_service_openapi_specs: dict[str, Any],
    webserver_service_openapi_specs: dict[str, Any],
    storage_service_openapi_specs: dict[str, Any],
    directorv2_service_openapi_specs: dict[str, Any],
) -> dict[str, Spec]:
    return {
        "catalog": create_spec(catalog_service_openapi_specs),
        "webserver": create_spec(webserver_service_openapi_specs),
        "storage": create_spec(storage_service_openapi_specs),
        "directorv2": create_spec(directorv2_service_openapi_specs),
    }


mock_folder_path = CURRENT_DIR.parent.parent / "mocks"
mock_folder_path.exists()


@pytest.mark.skipif(
    not OPENAPI_CORE_INSTALLED,
    reason="openapi-core is very restritive with jsonschema version and limits requirements/_base.txt",
)
@pytest.mark.parametrize(
    "mock_capture_path", mock_folder_path.glob("*.json"), ids=lambda p: p.name
)
def test_openapion_capture_mock(
    mock_capture_path: Path,
    openapi_specs: dict[str, Spec],
):
    assert mock_capture_path.exists()
    assert mock_capture_path.name.endswith(".json")

    captures = TypeAdapter(
        list[HttpApiCallCaptureModel] | HttpApiCallCaptureModel
    ).validate_json(mock_capture_path.read_text())

    if not isinstance(captures, list):
        captures = [
            captures,
        ]

    for capture in captures:
        # SEE https://openapi-core.readthedocs.io/en/latest/

        request = httpx.Request(
            method=capture.method,
            url=f"http://{capture.host}/{capture.path}",
            params=capture.query,
            json=capture.request_payload,
        )
        openapi_request = StarletteOpenAPIRequest(request)

        response = httpx.Response(
            status_code=capture.status_code,
            json=capture.response_body,
        )
        openapi_response = StarletteOpenAPIResponse(response)

        validate_request(openapi_specs[capture.host], openapi_request)
        validate_response(
            openapi_specs[capture.host],
            openapi_request,
            openapi_response,
        )


_CAPTURE_REGEX_TEST_CASES: list[tuple[str, str, str | None, str | None]] = [
    (
        "solver_key",
        """{
            "required": true,
            "schema": {
              "title": "Solver Key",
              "pattern": "^simcore/services/comp/([a-z0-9][a-z0-9_.-]*/)*([a-z0-9-_]+[a-z0-9])$",
              "type": "string"
            },
            "name": "solver_key",
            "in": "path"
          }""",
        "simcore/services/comp/itis/sleeper",
        "simcore/something",
    ),
    (
        "solver_version",
        r"""{
            "required": true,
            "schema": {
              "title": "Version",
              "pattern": "^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
              "type": "string"
            },
            "name": "version",
            "in": "path"
          }""",
        "2.0.2",
        "2.s.6",
    ),
    (
        "job_id",
        """{
            "required": true,
            "schema": {
              "title": "Job Id",
              "type": "string",
              "format": "uuid"
            },
            "name": "job_id",
            "in": "path"
          }""",
        "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "3fa85f64-5717-4562-b3fc-2c963f66",
    ),
    (
        "cluster_id",
        """{
            "required": false,
            "schema": {
              "title": "Cluster Id",
              "minimum": 0,
              "type": "integer"
            },
            "name": "cluster_id",
            "in": "query"
          }""",
        "15",
        "2i0",
    ),
    (
        "test_float",
        """{
            "required": false,
            "schema": {
              "title": "My float",
              "minimum": 0.3,
              "type": "float"
            },
            "name": "my_float",
            "in": "path"
          }""",
        "1.5",
        "20z",
    ),
    (
        "data_set_id",
        """{
            "required": true,
            "schema": {
              "title": "Dataset Id",
              "type": "string"
            },
            "name": "dataset_id",
            "in": "path"
          }""",
        "my_string123.;-",
        None,
    ),
]


@pytest.mark.parametrize("params", _CAPTURE_REGEX_TEST_CASES, ids=lambda x: x[0])
def test_param_regex_pattern(params: tuple[str, str, str, str]):
    _, openapi_param, match, non_match = params
    param: CapturedParameter = CapturedParameter(**json.loads(openapi_param))
    pattern = param.schema_.regex_pattern
    pattern = "^" + pattern + "$"
    if match is not None:
        assert re.match(
            pattern=pattern, string=match
        ), f"{match=} did not match {pattern=}"
    if non_match is not None:
        assert not re.match(
            pattern=pattern, string=non_match
        ), f"{non_match=} matched {pattern=}"


_API_SERVER_PATHS: list[tuple[str, Path, str]] = [
    (
        "get_solver",
        Path("/v0/solvers/{solver_key}/latest"),
        "/v0/solvers/simcore/services/comp/itis/sleeper/latest",
    ),
    (
        "get_job",
        Path("/v0/solvers/{solver_key}/releases/{version}/jobs/{job_id}"),
        "/v0/solvers/simcore/services/comp/itis/sleeper/releases/2.0.2/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    (
        "start_job",
        Path("/v0/solvers/{solver_key}/releases/{version}/jobs/{job_id}:start"),
        "/v0/solvers/simcore/services/comp/itis/sleeper/releases/2.0.2/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6:start",
    ),
    ("get_service_metadata", Path("/v0/meta"), "/v0/meta"),
]


@pytest.mark.parametrize("params", _API_SERVER_PATHS, ids=lambda x: x[0])
@respx.mock
def test_capture_respx_api_server(params: tuple[str, Path, str]):
    _, openapi_path, example = params
    assert _DUMMY_API_SERVER_OPENAPI.is_file()
    openapi_spec: dict[str, Any] = jsonref.loads(_DUMMY_API_SERVER_OPENAPI.read_text())
    url_path: PathDescription = _determine_path(
        openapi_spec=openapi_spec, response_path=openapi_path
    )
    path_pattern = str(openapi_path)
    for p in url_path.path_parameters:
        path_pattern = path_pattern.replace("{" + p.name + "}", p.respx_lookup)

    def side_effect(request, **kwargs):
        return httpx.Response(status_code=200, json=kwargs)

    my_route = respx.get(url__regex="https://example.org" + path_pattern).mock(
        side_effect=side_effect
    )
    response = httpx.get("https://example.org" + example)
    assert my_route.called
    assert response.status_code == 200
    assert all(param.name in response.json() for param in url_path.path_parameters)
