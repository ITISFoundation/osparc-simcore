# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import sys
from pathlib import Path
from typing import Any, TypeAlias

import httpx
import pytest
from pydantic import parse_file_as
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel

try:
    from openapi_core import Spec, create_spec, validate_request, validate_response
    from openapi_core.contrib.starlette import (
        StarletteOpenAPIRequest,
        StarletteOpenAPIResponse,
    )

    OPENAPI_CORE_INSTALLED = True
except ImportError:
    Spec: TypeAlias = Any
    StarletteOpenAPIRequest: TypeAlias = httpx.Request
    StarletteOpenAPIResponse: TypeAlias = httpx.Response
    OPENAPI_CORE_INSTALLED = False


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture
def openapi_specs(
    catalog_service_openapi_specs: dict[str, Any],
    webserver_service_openapi_specs: dict[str, Any],
) -> dict[str, Spec]:
    return {
        "catalog": create_spec(catalog_service_openapi_specs),
        "webserver": create_spec(webserver_service_openapi_specs),
    }


mock_folder_path = CURRENT_DIR.parent / "mocks"
mock_folder_path.exists()


@pytest.mark.skip_if(
    OPENAPI_CORE_INSTALLED,
    reason="openapi-core is very restritive with jsonschema version and limits requirements/_base.txt",
)
@pytest.mark.parametrize("mock_capture_path", mock_folder_path.glob("*.json"))
def test_mock_captures_against_openapi(
    mock_capture_path: Path,
    openapi_specs: dict[str, Spec],
):
    assert mock_capture_path.exists()
    assert mock_capture_path.name.endswith(".json")

    captures = parse_file_as(list[HttpApiCallCaptureModel], mock_capture_path)

    for capture in captures:
        request = httpx.Request(
            method=capture.method,
            url=f"http://{capture.host}/{capture.path}",
            params=capture.query,
            json=capture.request_payload,
        )
        response = httpx.Response(
            status_code=capture.status_code,
            json=capture.response_body,
        )

        # SEE https://openapi-core.readthedocs.io/en/latest/

        openapi_response = StarletteOpenAPIResponse(response)
        openapi_request = StarletteOpenAPIRequest(request)

        validate_request(openapi_specs[capture.host], openapi_request)
        validate_response(
            openapi_specs[capture.host],
            openapi_request,
            openapi_response,
        )
