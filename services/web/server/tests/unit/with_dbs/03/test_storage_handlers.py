# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
import urllib.parse
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from models_library.api_schemas_storage import (
    FileUploadCompleteResponse,
    FileUploadLinks,
    FileUploadSchema,
)
from pydantic import AnyUrl, ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.storage._handlers import (
    _from_storage_url,
    _to_storage_url,
)
from yarl import URL


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "STORAGE_HOST": "fake-storage",
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
        return TypeAdapter(AnyUrl).validate_python("http://private-url")

    mocker.patch(
        "simcore_service_webserver.storage._handlers._from_storage_url",
        autospec=True,
        side_effect=_resolve,
    )


MOCK_FILE_UPLOAD_SCHEMA = FileUploadSchema(
    chunk_size=TypeAdapter(ByteSize).validate_python("5GiB"),
    urls=[TypeAdapter(AnyUrl).validate_python("s3://file_id")],
    links=FileUploadLinks(
        abort_upload=TypeAdapter(AnyUrl).validate_python(
            "http://private-url/operation:abort"
        ),
        complete_upload=TypeAdapter(AnyUrl).validate_python(
            "http://private-url/operation:complete"
        ),
    ),
)

MOCK_FILE_UPLOAD_SCHEMA = FileUploadSchema.model_validate(
    {
        "chunk_size": "5",
        "urls": ["s3://file_id"],
        "links": {
            "abort_upload": "http://private-url/operation:abort",
            "complete_upload": "http://private-url/operation:complete",
        },
    },
)


MOCK_FILE_UPLOAD_COMPLETE_RESPONSE = FileUploadCompleteResponse.model_validate(
    {"links": {"state": "http://private-url"}}
)


DOUBLE_ENCODE_SLASH_IN_FILE_ID = "ef944bbe-14c7-11ee-a195-02420a0f07ab%252F46ac4913-92dc-432c-98e3-2dea21d3f0ed%252Fa_text_file.txt"
SINGLE_ENCODE_SLASH_IN_FILE_ID = "ef944bbe-14c7-11ee-a195-02420a0f07ab%2F46ac4913-92dc-432c-98e3-2dea21d3f0ed%2Fa_text_file.txt"


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "file_id", [SINGLE_ENCODE_SLASH_IN_FILE_ID, DOUBLE_ENCODE_SLASH_IN_FILE_ID]
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
            json.loads(MOCK_FILE_UPLOAD_SCHEMA.model_dump_json()),
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
            json.loads(MOCK_FILE_UPLOAD_COMPLETE_RESPONSE.model_dump_json()),
            id="complete_upload_file",
        ),
        pytest.param(
            "POST",
            "/v0/storage/locations/0/files/{file_id}:complete/futures/RANDOM_FUTURE_ID",
            None,
            json.loads(MOCK_FILE_UPLOAD_SCHEMA.model_dump_json()),
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


def test_url_storage_resolver_helpers(faker: Faker, app_environment: EnvVarsDict):

    app = web.Application()
    setup_settings(app)

    # NOTE: careful, first we need to encode the "/" in this file path.
    # For that we need safe="" option
    assert urllib.parse.quote("/") == "/"
    assert urllib.parse.quote("/", safe="") == "%2F"
    assert urllib.parse.quote("%2F", safe="") == "%252F"

    file_id = urllib.parse.quote(f"{faker.uuid4()}/{faker.uuid4()}/file.py", safe="")
    assert "%2F" in file_id
    assert "%252F" not in file_id

    url = URL(f"/v0/storage/locations/0/files/{file_id}:complete", encoded=True)
    assert url.raw_parts[-1] == f"{file_id}:complete"

    web_request = make_mocked_request("GET", str(url), app=app)
    web_request[RQT_USERID_KEY] = faker.pyint()

    # web -> storage
    storage_url = _to_storage_url(web_request)
    # Something like
    # http://storage:123/v5/locations/0/files/e3e70...c07cd%2Ff7...55%2Ffile.py:complete?user_id=8376

    assert storage_url.raw_parts[-1] == web_request.url.raw_parts[-1]

    assert storage_url.host == app_environment["STORAGE_HOST"]
    assert storage_url.port == int(app_environment["STORAGE_PORT"])
    assert storage_url.query["user_id"] == str(web_request[RQT_USERID_KEY])

    # storage -> web
    web_url: AnyUrl = _from_storage_url(
        web_request, TypeAdapter(AnyUrl).validate_python(f"{storage_url}")
    )

    assert storage_url.host != web_url.host
    assert storage_url.port != web_url.port

    assert isinstance(storage_url, URL)  # this is a bit inconvenient
    assert isinstance(web_url, AnyUrl)
    assert f"{web_url}" == f"{web_request.url}"
