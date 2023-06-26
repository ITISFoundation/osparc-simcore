# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import pytest
from openapi_core import Spec as OAS
from openapi_core import validate_request
from pydantic import parse_file_as
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel


@pytest.fixture
def api_server_oas(osparc_simcore_services_dir: Path) -> OAS:
    return OAS.from_file_path(
        osparc_simcore_services_dir / "api-server" / "openapi.json"
    )


@pytest.mark.parametrize("mock_name", ("on_list_jobs"))
def test_it(project_tests_dir: Path, mock_name: str, api_server_oas: OAS):
    mock_path = project_tests_dir / f"{mock_name}.json"

    captures = parse_file_as(list[HttpApiCallCaptureModel], mock_path)

    result = validate_request(request, spec=api_server_oas)
