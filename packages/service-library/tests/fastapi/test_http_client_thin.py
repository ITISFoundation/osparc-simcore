# pylint:disable=redefined-outer-name

import logging
from collections.abc import AsyncIterable, Iterable

import pytest
from httpx import (
    HTTPError,
    PoolTimeout,
    Request,
    RequestError,
    Response,
    TransportError,
    codes,
)
from pydantic import AnyHttpUrl, parse_obj_as
from respx import MockRouter
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    ClientHttpError,
    UnexpectedStatusError,
    expect_status,
    retry_on_errors,
)

# UTILS


class FakeThickClient(BaseThinClient):
    @retry_on_errors
    async def get_provided_url(self, provided_url: str) -> Response:
        return await self.client.get(provided_url)

    @retry_on_errors
    async def get_retry_for_status(self) -> Response:
        return await self.client.get("http://missing-host:1111")


def _assert_messages(messages: list[str]) -> None:
    # check if the right amount of messages was captured by the logs
    unexpected_counter = 1
    for log_message in messages:
        if log_message.startswith("Retrying"):
            assert "as it raised" in log_message
            continue
        assert log_message.startswith(f"Request timed-out after {unexpected_counter}")
        unexpected_counter += 1


@pytest.fixture()
def caplog_info_level(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.INFO):
        yield caplog


@pytest.fixture
def request_timeout() -> int:
    # below refer to exponential wait step duration
    return 1 + 2


@pytest.fixture
async def thick_client(request_timeout: int) -> AsyncIterable[FakeThickClient]:
    async with FakeThickClient(request_timeout=request_timeout) as client:
        yield client


@pytest.fixture
def test_url() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://missing-host:1111")


async def test_connection_error(
    thick_client: FakeThickClient, test_url: AnyHttpUrl
) -> None:
    with pytest.raises(ClientHttpError) as exe_info:
        await thick_client.get_provided_url(test_url)

    assert isinstance(exe_info.value, ClientHttpError)
    assert isinstance(exe_info.value.error, TransportError)


async def test_retry_on_errors(
    request_timeout: int,
    test_url: AnyHttpUrl,
    caplog_info_level: pytest.LogCaptureFixture,
) -> None:
    client = FakeThickClient(request_timeout=request_timeout)

    with pytest.raises(ClientHttpError):
        await client.get_provided_url(test_url)

    _assert_messages(caplog_info_level.messages)


@pytest.mark.parametrize("error_class", [TransportError, PoolTimeout])
async def test_retry_on_errors_by_error_type(
    error_class: type[RequestError],
    caplog_info_level: pytest.LogCaptureFixture,
    request_timeout: int,
    test_url: AnyHttpUrl,
) -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors
        async def raises_request_error(self) -> Response:
            raise error_class(
                "mock_connect_error",  # noqa: EM101
                request=Request(method="GET", url=test_url),
            )

    client = ATestClient(request_timeout=request_timeout)

    with pytest.raises(ClientHttpError):
        await client.raises_request_error()

    if error_class == PoolTimeout:
        _assert_messages(caplog_info_level.messages[:-1])
        connections_message = caplog_info_level.messages[-1]
        assert (
            connections_message
            == "Pool status @ 'POOL TIMEOUT': requests(0)=[], connections(0)=[]"
        )
    else:
        _assert_messages(caplog_info_level.messages)


async def test_retry_on_errors_raises_client_http_error(
    request_timeout: int,
) -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors
        async def raises_http_error(self) -> Response:
            msg = "mock_http_error"
            raise HTTPError(msg)

    client = ATestClient(request_timeout=request_timeout)

    with pytest.raises(ClientHttpError):
        await client.raises_http_error()


async def test_methods_do_not_return_response(
    request_timeout: int,
) -> None:
    class OKTestClient(BaseThinClient):
        async def public_method_ok(self) -> Response:  # type: ignore
            """this method will be ok even if no code is used"""

    # OK
    OKTestClient(request_timeout=request_timeout)

    class FailWrongAnnotationTestClient(BaseThinClient):
        async def public_method_wrong_annotation(self) -> None:
            """this method will raise an error"""

    with pytest.raises(AssertionError, match="should return an instance"):
        FailWrongAnnotationTestClient(request_timeout=request_timeout)

    class FailNoAnnotationTestClient(BaseThinClient):
        async def public_method_no_annotation(self):
            """this method will raise an error"""

    with pytest.raises(AssertionError, match="should return an instance"):
        FailNoAnnotationTestClient(request_timeout=request_timeout)


async def test_expect_state_decorator(
    test_url: AnyHttpUrl,
    respx_mock: MockRouter,
    request_timeout: int,
) -> None:
    url_get_200_ok = f"{test_url}/ok"
    get_wrong_state = f"{test_url}/wrong-state"
    error_status = codes.NOT_FOUND

    class ATestClient(BaseThinClient):
        @expect_status(codes.OK)
        async def get_200_ok(self) -> Response:
            return await self.client.get(url_get_200_ok)

        @expect_status(error_status)
        async def get_wrong_state(self) -> Response:
            return await self.client.get(get_wrong_state)

    respx_mock.get(url_get_200_ok).mock(return_value=Response(codes.OK))
    respx_mock.get(get_wrong_state).mock(return_value=Response(codes.OK))

    test_client = ATestClient(request_timeout=request_timeout)

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
