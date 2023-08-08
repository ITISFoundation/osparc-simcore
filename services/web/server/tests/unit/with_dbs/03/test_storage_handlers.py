# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_storage import (
    FileUploadCompleteResponse,
    FileUploadLinks,
    FileUploadSchema,
)
from pydantic import AnyUrl, ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from simcore_postgres_database.models.users import UserRole


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
        },
    )


@pytest.fixture
def mock_request_storage(mocker: MockerFixture, expected_response: Any) -> None:
    async def _resp(*args, **kwargs) -> tuple[Any, int]:
        return (wrap_as_envelope(data=expected_response), 200)

    mocker.patch(
        "simcore_service_webserver.storage._handlers._forward_request_to_storage",
        autospec=True,
        side_effect=_resp,
    )

    def _resolve(*args, **kwargs) -> AnyUrl:
        return parse_obj_as(AnyUrl, "http://private-url")

    mocker.patch(
        "simcore_service_webserver.storage._handlers._unresolve_storage_url",
        autospec=True,
        side_effect=_resolve,
    )


MOCK_FILE_UPLOAD_SCHEMA = FileUploadSchema(
    chunk_size=parse_obj_as(ByteSize, "5GiB"),
    urls=[parse_obj_as(AnyUrl, "s3://file_id")],
    links=FileUploadLinks(
        abort_upload=parse_obj_as(AnyUrl, "http://private-url/operation:abort"),
        complete_upload=parse_obj_as(AnyUrl, "http://private-url/operation:complete"),
    ),
)

MOCK_FILE_UPLOAD_SCHEMA = parse_obj_as(
    FileUploadSchema,
    {
        "chunk_size": "5",
        "urls": ["s3://file_id"],
        "links": {
            "abort_upload": "http://private-url/operation:abort",
            "complete_upload": "http://private-url/operation:complete",
        },
    },
)


MOCK_FILE_UPLOAD_COMPLETE_RESPONSE = parse_obj_as(
    FileUploadCompleteResponse, {"links": {"state": "http://private-url"}}
)


DOUBLE_ENCODE_SLASH_IN_FILE_ID = "ef944bbe-14c7-11ee-a195-02420a0f07ab%252F46ac4913-92dc-432c-98e3-2dea21d3f0ed%252Fa_text_file.txt"
SINGLE_ENCODE_SLASH_IN_FILE_ID = "ef944bbe-14c7-11ee-a195-02420a0f07ab%2F46ac4913-92dc-432c-98e3-2dea21d3f0ed%2Fa_text_file.txt"


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "file_id", [DOUBLE_ENCODE_SLASH_IN_FILE_ID, SINGLE_ENCODE_SLASH_IN_FILE_ID]
)
@pytest.mark.parametrize(
    "method, path, body, expected_response",
    [
        pytest.param(
            "GET",
            "/v0/storage/locations/0/files/{file_id}/metadata",
            None,
            "",
            id="get_file_metadata",
        ),
        pytest.param(
            "GET",
            "/v0/storage/locations/0/files/{file_id}",
            None,
            "",
            id="download_file",
        ),
        pytest.param(
            "PUT",
            "/v0/storage/locations/0/files/{file_id}",
            None,
            json.loads(MOCK_FILE_UPLOAD_SCHEMA.json()),
            id="upload_file",
        ),
        pytest.param(
            "DELETE",
            "/v0/storage/locations/0/files/{file_id}",
            None,
            "",
            id="delete_file",
        ),
        pytest.param(
            "POST",
            "/v0/storage/locations/0/files/{file_id}:abort",
            None,
            "",
            id="abort_upload_file",
        ),
        pytest.param(
            "POST",
            "/v0/storage/locations/0/files/{file_id}:complete",
            {"parts": []},
            json.loads(MOCK_FILE_UPLOAD_COMPLETE_RESPONSE.json()),
            id="complete_upload_file",
        ),
        pytest.param(
            "POST",
            "/v0/storage/locations/0/files/{file_id}:complete/futures/RANDOM_FUTURE_ID",
            None,
            json.loads(MOCK_FILE_UPLOAD_SCHEMA.json()),
            id="is_completed_upload_file",
        ),
    ],
)
async def test_openapi_regression_test(
    mock_request_storage: None,
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    file_id: str,
    method: str,
    path: str,
    body,
    expected_response: Any,
):
    response = await client.request(method, path.format(file_id=file_id), json=body)
    decoded_response = await response.json()
    assert decoded_response["error"] is None
    assert decoded_response["data"] is not None
