# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import logging
from collections.abc import AsyncIterator
from typing import Final

import httpx
import httpx2
import pytest
import respx
from pydantic import AnyUrl, SecretStr
from simcore_service_webserver.fogbugz._client import (
    FogbugzCaseCreate,
    FogbugzRestClient,
)

_FAKE_API_TOKEN: Final[str] = "synthetic-fogbugz-token-do-not-log"  # noqa: S105
_BASE_URL: Final[str] = "https://fogbugz.dummy.test"
_JSON_API_PATH: Final[str] = "/f/api/0/jsonapi"

_CASE: Final[FogbugzCaseCreate] = FogbugzCaseCreate(
    fogbugz_project_id=45,
    title="support case",
    description="synthetic customer reported failure detail",
)


@pytest.fixture
async def fogbugz_client() -> AsyncIterator[FogbugzRestClient]:
    async with FogbugzRestClient(
        api_token=SecretStr(_FAKE_API_TOKEN),
        base_url=AnyUrl(_BASE_URL),
    ) as client:
        yield client


async def test_api_token_absent_from_logs_on_http_error(
    caplog: pytest.LogCaptureFixture,
    fogbugz_client: FogbugzRestClient,
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(f"{_BASE_URL}{_JSON_API_PATH}").mock(
        return_value=httpx.Response(400, json={"error": "invalid request"})
    )

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(httpx2.HTTPStatusError),
    ):
        await fogbugz_client.create_case(data=_CASE)

    assert _FAKE_API_TOKEN not in caplog.text
    assert "new" in caplog.text


async def test_api_request_sends_token_to_fogbugz(
    fogbugz_client: FogbugzRestClient,
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(f"{_BASE_URL}{_JSON_API_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"case": {"ixBug": "12345"}}})
    )

    case_id = await fogbugz_client.create_case(data=_CASE)
    assert case_id == "12345"

    request = respx_mock.calls.last.request
    body = request.content.decode()
    assert '"cmd": "new"' in body
    assert _FAKE_API_TOKEN in body
