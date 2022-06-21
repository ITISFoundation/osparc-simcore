# pylint:disable=redefined-outer-name

import pytest
from _pytest.logging import LogCaptureFixture
from httpx import ConnectError, Response, codes
from pydantic import AnyHttpUrl, parse_obj_as
from respx import MockRouter
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._base import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._errors import (
    ClientTransportError,
    UnexpectedStatusError,
    WrongReturnType,
)

pytestmark = pytest.mark.asyncio

# UTILS


class TestThickClient(BaseThinClient):
    @retry_on_errors
    async def get_provided_url(self, provided_url: str) -> Response:
        return await self._client.get(provided_url)

    @retry_on_errors
    async def get_retry_for_status(self) -> Response:
        return await self._client.get("http://some-test.url")


# FIXTURES


@pytest.fixture
def thick_client() -> TestThickClient:
    return TestThickClient(request_max_retries=1)


@pytest.fixture
def test_url() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://some-host:8008")


# TESTS


async def test_connection_error(
    thick_client: TestThickClient, test_url: AnyHttpUrl
) -> None:
    with pytest.raises(ConnectError):
        await thick_client.get_provided_url(test_url)


@pytest.mark.parametrize("retry_count", [2, 1])
async def test_connection_error_retry(
    retry_count: int, test_url: AnyHttpUrl, caplog_info_level: LogCaptureFixture
) -> None:
    client = TestThickClient(request_max_retries=retry_count)

    with pytest.raises(ConnectError):
        await client.get_provided_url(test_url)

    # check if the right amount of messages was captured by the logs
    assert len(caplog_info_level.messages) == retry_count
    for i, log_message in enumerate(caplog_info_level.messages):
        assert log_message.startswith(
            f"[{i+1}/{retry_count}]Retry. Unexpected ConnectError"
        )


async def test_(thick_client: TestThickClient) -> None:
    with pytest.raises(ClientTransportError):
        await thick_client.get_provided_url("some.fake-url")


async def test_methods_do_not_return_response() -> None:
    class ATestClient(BaseThinClient):
        async def public_method_ok(self) -> Response:  # type: ignore
            """this method will be ok even if no code is used"""

        async def public_method_false(self) -> None:
            """this method will raise an error"""

    with pytest.raises(WrongReturnType):
        ATestClient(request_max_retries=1)


async def test_expect_state_decorator(
    test_url: AnyHttpUrl, respx_mock: MockRouter
) -> None:

    url_get_200_ok = f"{test_url}/ok"
    get_wrong_state = f"{test_url}/wrong-state"
    error_status = codes.NOT_FOUND

    class ATestClient(BaseThinClient):
        @expect_status(codes.OK)
        async def get_200_ok(self) -> Response:
            return await self._client.get(url_get_200_ok)

        @expect_status(error_status)
        async def get_wrong_state(self) -> Response:
            return await self._client.get(get_wrong_state)

    respx_mock.get(url_get_200_ok).mock(return_value=Response(codes.OK))
    respx_mock.get(get_wrong_state).mock(return_value=Response(codes.OK))

    test_client = ATestClient(request_max_retries=1)

    # OK
    response = await test_client.get_200_ok()
    assert response.status_code == codes.OK

    # RAISES EXPECTED ERROR
    with pytest.raises(UnexpectedStatusError) as err_info:
        await test_client.get_wrong_state()

    assert err_info.value.response.status_code == codes.OK
    assert (
        f"{err_info.value}"
        == f"Expected status: {error_status}, got {codes.OK} for: {get_wrong_state}: headers=Headers({{}}), body=''"
    )
