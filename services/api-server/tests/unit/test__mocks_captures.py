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
import pytest
from pydantic import parse_file_as
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from simcore_service_api_server.utils.http_calls_capture_processing import Param

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


mock_folder_path = CURRENT_DIR.parent / "mocks"
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

    captures = parse_file_as(
        list[HttpApiCallCaptureModel] | HttpApiCallCaptureModel, mock_capture_path
    )

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


_CAPTURE_REGEX_TEST_CASES: list[tuple[str, str, str, str]] = [
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
]


@pytest.mark.parametrize("params", _CAPTURE_REGEX_TEST_CASES, ids=lambda x: x[0])
def test_param_regex_pattern(params: tuple[str, str, str, str]):
    _, openapi_param, match, non_match = params
    param: Param = Param(**json.loads(openapi_param))
    pattern = param.param_schema.regex_pattern
    assert re.match(pattern=pattern, string=match), f"{match=} did not match {pattern=}"
    assert not re.match(
        pattern=pattern, string=non_match
    ), f"{non_match=} matched {pattern=}"
