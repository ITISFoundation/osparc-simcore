# pylint:disable=redefined-outer-name

import pytest
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
from pytest import LogCaptureFixture
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


def _assert_messages(messages: list[str]) -> None:
    # check if the right amount of messages was captured by the logs
    unexpected_counter = 1
    for log_message in messages:
        if log_message.startswith("Retrying"):
            assert "as it raised" in log_message
            continue
        assert log_message.startswith("Unexpected error")
        assert log_message.endswith(f"(attempt {unexpected_counter})")
        unexpected_counter += 1


@pytest.fixture
def request_max_network_issues_tolerance_s() -> int:
    # below refer to exponential wait step duration
    return 1 + 2


@pytest.fixture
def thick_client(request_max_network_issues_tolerance_s: int) -> FakeThickClient:
    return FakeThickClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    )


@pytest.fixture
def test_url() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://missing-host:1111")


async def test_base_with_async_context_manager(
    test_url: AnyHttpUrl, request_max_network_issues_tolerance_s: int
) -> None:
    async with FakeThickClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    ) as client:
        with pytest.raises(ClientHttpError):
            await client.get_provided_url(test_url)


async def test_connection_error(
    thick_client: FakeThickClient, test_url: AnyHttpUrl
) -> None:
    with pytest.raises(ClientHttpError) as exe_info:
        await thick_client.get_provided_url(test_url)

    assert isinstance(exe_info.value, ClientHttpError)
    assert isinstance(exe_info.value.error, ConnectError)


async def test_retry_on_errors(
    request_max_network_issues_tolerance_s: int,
    test_url: AnyHttpUrl,
    caplog_info_level: LogCaptureFixture,
) -> None:
    client = FakeThickClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    )

    with pytest.raises(ClientHttpError):
        await client.get_provided_url(test_url)

    _assert_messages(caplog_info_level.messages)


@pytest.mark.parametrize("error_class", [ConnectError, PoolTimeout])
async def test_retry_on_errors_by_error_type(
    error_class: type[RequestError],
    caplog_info_level: LogCaptureFixture,
    request_max_network_issues_tolerance_s: int,
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

    client = ATestClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    )

    with pytest.raises(ClientHttpError):
        await client.raises_request_error()

    if error_class == PoolTimeout:
        _assert_messages(caplog_info_level.messages[:-1])
        connections_message = caplog_info_level.messages[-1]
        assert connections_message == "Requests while event 'POOL TIMEOUT': []"
    else:
        _assert_messages(caplog_info_level.messages)


async def test_retry_on_errors_raises_client_http_error(
    request_max_network_issues_tolerance_s: int,
) -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors
        async def raises_http_error(self) -> Response:
            raise HTTPError("mock_http_error")

    client = ATestClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    )

    with pytest.raises(ClientHttpError):
        await client.raises_http_error()


async def test_methods_do_not_return_response(
    request_max_network_issues_tolerance_s: int,
) -> None:
    class OKTestClient(BaseThinClient):
        async def public_method_ok(self) -> Response:  # type: ignore
            """this method will be ok even if no code is used"""

    # OK
    OKTestClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    )

    class FailWrongAnnotationTestClient(BaseThinClient):
        async def public_method_wrong_annotation(self) -> None:
            """this method will raise an error"""

    with pytest.raises(_WrongReturnType):
        FailWrongAnnotationTestClient(
            request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
        )

    class FailNoAnnotationTestClient(BaseThinClient):
        async def public_method_no_annotation(self):
            """this method will raise an error"""

    with pytest.raises(_WrongReturnType):
        FailNoAnnotationTestClient(
            request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
        )


async def test_expect_state_decorator(
    test_url: AnyHttpUrl,
    respx_mock: MockRouter,
    request_max_network_issues_tolerance_s: int,
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

    test_client = ATestClient(
        request_max_network_issues_tolerance_s=request_max_network_issues_tolerance_s
    )

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
