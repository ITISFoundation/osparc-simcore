# pylint:disable=redefined-outer-name

import pytest
from _pytest.logging import LogCaptureFixture
from httpx import (
    ConnectError,
    HTTPError,
    PoolTimeout,
    Request,
    RequestError,
    Response,
    codes,
)
from pydantic import AnyHttpUrl, parse_obj_as
from respx import MockRouter
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._base import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._errors import (
    ClientHttpError,
    UnexpectedStatusError,
    _WrongReturnType,
)

# UTILS


class FakeThickClient(BaseThinClient):
    @retry_on_errors
    async def get_provided_url(self, provided_url: str) -> Response:
        return await self._client.get(provided_url)

    @retry_on_errors
    async def get_retry_for_status(self) -> Response:
        return await self._client.get("http://missing-host:1111")


# FIXTURES


@pytest.fixture
def thick_client() -> FakeThickClient:
    return FakeThickClient(request_max_retries=1)


@pytest.fixture
def test_url() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://missing-host:1111")


# TESTS


async def test_base_with_async_context_manager(test_url: AnyHttpUrl) -> None:
    async with FakeThickClient(request_max_retries=1) as client:
        with pytest.raises(ClientHttpError):
            await client.get_provided_url(test_url)


async def test_connection_error(
    thick_client: FakeThickClient, test_url: AnyHttpUrl
) -> None:
    with pytest.raises(ClientHttpError) as exe_info:
        await thick_client.get_provided_url(test_url)

    assert isinstance(exe_info.value, ClientHttpError)
    assert isinstance(exe_info.value.error, ConnectError)


@pytest.mark.parametrize("retry_count", [2, 1])
async def test_retry_on_errors(
    retry_count: int, test_url: AnyHttpUrl, caplog_info_level: LogCaptureFixture
) -> None:
    client = FakeThickClient(request_max_retries=retry_count)

    with pytest.raises(ClientHttpError):
        await client.get_provided_url(test_url)

    # check if the right amount of messages was captured by the logs
    assert len(caplog_info_level.messages) == retry_count
    for i, log_message in enumerate(caplog_info_level.messages):
        assert log_message.startswith(
            f"[{i+1}/{retry_count}]Retry. Unexpected ConnectError"
        )


@pytest.mark.parametrize("error_class", [ConnectError, PoolTimeout])
@pytest.mark.parametrize("retry_count", [1, 2])
async def test_retry_on_errors_by_error_type(
    error_class: type[RequestError],
    caplog_info_level: LogCaptureFixture,
    retry_count: int,
    test_url: AnyHttpUrl,
) -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors
        async def raises_request_error(self) -> Response:
            raise error_class(
                "mock_connect_error",
                request=Request(method="GET", url=test_url),
            )

    client = ATestClient(request_max_retries=retry_count)

    with pytest.raises(ClientHttpError):
        await client.raises_request_error()

    log_count = retry_count + 1 if error_class == PoolTimeout else retry_count
    assert len(caplog_info_level.messages) == log_count

    if error_class == PoolTimeout:
        for i, retry_message in enumerate(caplog_info_level.messages[:-1]):
            assert retry_message.startswith(
                f"[{i+1}/{retry_count}]Retry. Unexpected PoolTimeout"
            )
        connections_message = caplog_info_level.messages[-1]
        assert connections_message == "Requests while event 'POOL TIMEOUT': []"
    else:
        for i, log_message in enumerate(caplog_info_level.messages):
            assert log_message.startswith(
                f"[{i+1}/{retry_count}]Retry. Unexpected ConnectError"
            )


async def test_retry_on_errors_raises_client_http_error() -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors
        async def raises_http_error(self) -> Response:
            raise HTTPError("mock_http_error")

    client = ATestClient(request_max_retries=1)

    with pytest.raises(ClientHttpError):
        await client.raises_http_error()


async def test_methods_do_not_return_response() -> None:
    class OKTestClient(BaseThinClient):
        async def public_method_ok(self) -> Response:  # type: ignore
            """this method will be ok even if no code is used"""

    # OK
    OKTestClient(request_max_retries=1)

    class FailWrongAnnotationTestClient(BaseThinClient):
        async def public_method_wrong_annotation(self) -> None:
            """this method will raise an error"""

    with pytest.raises(_WrongReturnType):
        FailWrongAnnotationTestClient(request_max_retries=1)

    class FailNoAnnotationTestClient(BaseThinClient):
        async def public_method_no_annotation(self):
            """this method will raise an error"""

    with pytest.raises(_WrongReturnType):
        FailNoAnnotationTestClient(request_max_retries=1)


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
