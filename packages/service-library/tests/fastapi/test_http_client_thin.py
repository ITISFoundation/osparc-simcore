# pylint:disable=redefined-outer-name

import logging
from collections.abc import AsyncIterable, Iterable
from typing import Final
from unittest import mock

import arrow
import httpx
import pytest
from httpx import HTTPError, PoolTimeout, Request, RequestError, Response, TransportError, codes
from pydantic import AnyHttpUrl, TypeAdapter
from respx import MockRouter
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    ClientHttpError,
    UnexpectedStatusError,
    _get_shared_ssl_context,
    expect_status,
    retry_on_errors,
)
from servicelib.tracing import TracingConfig

_TIMEOUT_OVERWRITE: Final[int] = 1

# UTILS


class FakeThickClient(BaseThinClient):
    @retry_on_errors()
    async def get_provided_url(self, provided_url: str) -> Response:
        return await self.client.get(provided_url)

    @retry_on_errors()
    async def normal_timeout(self) -> Response:
        return await self.client.get("http://missing-host:1111")

    @retry_on_errors(total_retry_timeout_overwrite=_TIMEOUT_OVERWRITE)
    async def overwritten_timeout(self) -> Response:
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
    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    async with FakeThickClient(total_retry_interval=request_timeout, tracing_config=tracing_config) as client:
        yield client


@pytest.fixture
def test_url() -> str:
    url = TypeAdapter(AnyHttpUrl).validate_python("http://missing-host:1111")
    return f"{url}"


async def test_connection_error(
    thick_client: FakeThickClient,
    test_url: str,
) -> None:
    with pytest.raises(ClientHttpError) as exe_info:
        await thick_client.get_provided_url(test_url)

    assert isinstance(exe_info.value, ClientHttpError)
    assert isinstance(exe_info.value.error, TransportError)


async def test_retry_on_errors(
    request_timeout: int,
    test_url: str,
    caplog_info_level: pytest.LogCaptureFixture,
) -> None:
    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    client = FakeThickClient(total_retry_interval=request_timeout, tracing_config=tracing_config)

    with pytest.raises(ClientHttpError):
        await client.get_provided_url(test_url)

    _assert_messages(caplog_info_level.messages)


@pytest.mark.parametrize("error_class", [TransportError, PoolTimeout])
async def test_retry_on_errors_by_error_type(
    error_class: type[RequestError],
    caplog_info_level: pytest.LogCaptureFixture,
    request_timeout: int,
    test_url: str,
) -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors()
        async def raises_request_error(self) -> Response:
            raise error_class(
                "mock_connect_error",  # noqa: EM101
                request=Request(method="GET", url=test_url),
            )

    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    client = ATestClient(total_retry_interval=request_timeout, tracing_config=tracing_config)

    with pytest.raises(ClientHttpError):
        await client.raises_request_error()

    if error_class == PoolTimeout:
        _assert_messages(caplog_info_level.messages[:-1])
        connections_message = caplog_info_level.messages[-1]
        assert connections_message == "Pool status @ 'POOL TIMEOUT': requests(0)=[], connections(0)=[]"
    else:
        _assert_messages(caplog_info_level.messages)


async def test_retry_on_errors_raises_client_http_error(
    request_timeout: int,
) -> None:
    class ATestClient(BaseThinClient):
        # pylint: disable=no-self-use
        @retry_on_errors()
        async def raises_http_error(self) -> Response:
            msg = "mock_http_error"
            raise HTTPError(msg)

    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    client = ATestClient(total_retry_interval=request_timeout, tracing_config=tracing_config)

    with pytest.raises(ClientHttpError):
        await client.raises_http_error()


def test_ssl_context_is_built_once_and_shared(request_timeout: int):
    class ATestClient(BaseThinClient): ...

    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    _get_shared_ssl_context.cache_clear()

    with mock.patch(
        "servicelib.fastapi.http_client_thin.create_ssl_context",
        wraps=httpx.create_ssl_context,
    ) as mocked_factory:
        clients = [ATestClient(total_retry_interval=request_timeout, tracing_config=tracing_config) for _ in range(3)]

    assert mocked_factory.call_count == 1

    contexts = {id(c.client._transport._pool._ssl_context) for c in clients}  # noqa: SLF001
    assert len(contexts) == 1
    assert contexts == {id(_get_shared_ssl_context())}


def test_shared_ssl_context_keeps_httpx_trust_store():
    _get_shared_ssl_context.cache_clear()

    def _ca_serials(context):
        return {cert["serialNumber"] for cert in context.get_ca_certs()}

    assert _ca_serials(_get_shared_ssl_context()) == _ca_serials(httpx.create_ssl_context())


async def test_methods_do_not_return_response(
    request_timeout: int,
) -> None:
    class OKTestClient(BaseThinClient):
        async def public_method_ok(self) -> Response:  # type: ignore
            """this method will be ok even if no code is used"""

    # OK
    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    OKTestClient(total_retry_interval=request_timeout, tracing_config=tracing_config)

    class FailWrongAnnotationTestClient(BaseThinClient):
        async def public_method_wrong_annotation(self) -> None:
            """this method will raise an error"""

    with pytest.raises(AssertionError, match="should return an instance"):
        FailWrongAnnotationTestClient(
            total_retry_interval=request_timeout,
            tracing_config=tracing_config,
        )

    class FailNoAnnotationTestClient(BaseThinClient):
        async def public_method_no_annotation(self):
            """this method will raise an error"""

    with pytest.raises(AssertionError, match="should return an instance"):
        FailNoAnnotationTestClient(
            total_retry_interval=request_timeout,
            tracing_config=tracing_config,
        )


async def test_expect_state_decorator(
    test_url: str,
    respx_mock: MockRouter,
    request_timeout: int,
) -> None:
    url_get_200_ok = f"{test_url}ok"
    get_wrong_state = f"{test_url}wrong-state"
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

    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    test_client = ATestClient(total_retry_interval=request_timeout, tracing_config=tracing_config)

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


async def test_retry_timeout_overwrite(
    request_timeout: int,
    caplog_info_level: pytest.LogCaptureFixture,
) -> None:
    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    client = FakeThickClient(total_retry_interval=request_timeout, tracing_config=tracing_config)

    caplog_info_level.clear()
    start = arrow.utcnow()
    with pytest.raises(ClientHttpError):
        await client.normal_timeout()

    normal_duration = (arrow.utcnow() - start).total_seconds()
    assert normal_duration >= request_timeout
    _assert_messages(caplog_info_level.messages)

    caplog_info_level.clear()
    start = arrow.utcnow()
    with pytest.raises(ClientHttpError):
        await client.overwritten_timeout()
    overwritten_duration = (arrow.utcnow() - start).total_seconds()
    assert overwritten_duration >= _TIMEOUT_OVERWRITE
    _assert_messages(caplog_info_level.messages)
