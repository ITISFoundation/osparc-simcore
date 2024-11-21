import asyncio
import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from common_library.errors_classes import OsparcErrorMixin
from httpx import AsyncClient, ConnectError, HTTPError, PoolTimeout, Response
from httpx._types import TimeoutTypes, URLTypes
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from settings_library.tracing import TracingSettings
from tenacity import RetryCallState
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential

from .http_client import BaseHTTPApi

_logger = logging.getLogger(__name__)


"""
Exception hierarchy:

* BaseClientError
  x BaseRequestError
    + ClientHttpError
    + UnexpectedStatusError
"""


class BaseClientError(OsparcErrorMixin, Exception):
    """Used as based for all the raised errors"""

    msg_template: str = "{message}"


class BaseHttpClientError(BaseClientError):
    """Base class to wrap all http related client errors"""


class ClientHttpError(BaseHttpClientError):
    """used to captures all httpx.HttpError"""

    msg_template: str = "Received httpx.HTTPError: {error}"


class UnexpectedStatusError(BaseHttpClientError):
    """raised when the status of the request is not the one it was expected"""

    msg_template: str = (
        "Expected status: {expecting}, got {response.status_code} for: {response.url}: "
        "headers={response.headers}, body='{response.text}'"
    )


def _log_pool_status(client: AsyncClient, event_name: str) -> None:
    # pylint: disable=protected-access
    pool = client._transport._pool  # type: ignore[attr-defined] # noqa: SLF001
    _logger.warning(
        "Pool status @ '%s': requests(%s)=%s, connections(%s)=%s",
        event_name.upper(),
        len(pool._requests),  # noqa: SLF001
        [
            (id(r), r.request.method, r.request.url, r.request.headers)
            for r in pool._requests  # noqa: SLF001
        ],
        len(pool.connections),
        [(id(c), c.__dict__) for c in pool.connections],
    )


def _after_log(log: logging.Logger) -> Callable[[RetryCallState], None]:
    def log_it(retry_state: RetryCallState) -> None:
        # pylint: disable=protected-access

        assert retry_state.outcome  # nosec
        e = retry_state.outcome.exception()
        assert isinstance(e, HTTPError)  # nosec
        log.error(
            "Request timed-out after %s attempts with an unexpected error: '%s':%s",
            retry_state.attempt_number,
            f"{e.request=}",
            f"{e=}",
        )

    return log_it


def _assert_public_interface(
    obj: object, extra_allowed_method_names: set[str] | None = None
) -> None:
    # makes sure all user public defined methods return `httpx.Response`

    _allowed_names: set[str] = {
        "setup_client",
        "teardown_client",
        "from_client_kwargs",
    }
    if extra_allowed_method_names:
        _allowed_names |= extra_allowed_method_names

    public_methods = [
        t[1]
        for t in inspect.getmembers(obj, predicate=inspect.ismethod)
        if not (t[0].startswith("_") or t[0] in _allowed_names)
    ]

    for method in public_methods:
        signature = inspect.signature(method)
        assert signature.return_annotation == Response, (
            f"{method=} should return an instance "
            f"of {Response}, not '{signature.return_annotation}'!"
        )


def retry_on_errors(
    total_retry_timeout_overwrite: float | None = None,
) -> Callable[..., Callable[..., Awaitable[Response]]]:
    """
    Will retry the request on `ConnectError` and `PoolTimeout`.
    Also wraps `httpx.HTTPError`
    raises:
    - `ClientHttpError`
    """

    def decorator(
        request_func: Callable[..., Awaitable[Response]]
    ) -> Callable[..., Awaitable[Response]]:
        assert asyncio.iscoroutinefunction(request_func)

        @functools.wraps(request_func)
        async def request_wrapper(zelf: "BaseThinClient", *args, **kwargs) -> Response:
            # pylint: disable=protected-access
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_delay(
                        total_retry_timeout_overwrite
                        if total_retry_timeout_overwrite
                        else zelf.total_retry_interval
                    ),
                    wait=wait_exponential(min=1),
                    retry=retry_if_exception_type((ConnectError, PoolTimeout)),
                    before_sleep=before_sleep_log(_logger, logging.WARNING),
                    after=_after_log(_logger),
                    reraise=True,
                ):
                    with attempt:
                        return await request_func(zelf, *args, **kwargs)
            except HTTPError as e:
                if isinstance(e, PoolTimeout):
                    _log_pool_status(zelf.client, "pool timeout")
                raise ClientHttpError(error=e) from e

            # NOTE: this satisfies mypy, both exceptions from retrial are HTTPError
            msg = "Unexpected error!"
            raise NotImplementedError(msg)

        return request_wrapper

    return decorator


def expect_status(
    expected_code: int,
) -> Callable[..., Callable[..., Awaitable[Response]]]:
    """
    raises an `UnexpectedStatusError` if the request's status is different
    from `expected_code`
    NOTE: always apply after `retry_on_errors`

    raises:
    - `UnexpectedStatusError`
    - `ClientHttpError`
    """

    def decorator(
        request_func: Callable[..., Awaitable[Response]]
    ) -> Callable[..., Awaitable[Response]]:
        assert asyncio.iscoroutinefunction(request_func)

        @functools.wraps(request_func)
        async def request_wrapper(zelf: "BaseThinClient", *args, **kwargs) -> Response:
            response = await request_func(zelf, *args, **kwargs)
            if response.status_code != expected_code:
                raise UnexpectedStatusError(response=response, expecting=expected_code)

            return response

        return request_wrapper

    return decorator


class BaseThinClient(BaseHTTPApi):
    def __init__(
        self,
        *,
        total_retry_interval: float,
        base_url: URLTypes | None = None,
        default_http_client_timeout: TimeoutTypes | None = None,
        extra_allowed_method_names: set[str] | None = None,
        tracing_settings: TracingSettings | None,
    ) -> None:
        _assert_public_interface(self, extra_allowed_method_names)

        self.total_retry_interval: float = total_retry_interval

        client_args: dict[str, Any] = {
            # NOTE: the default httpx pool limit configurations look good
            # https://www.python-httpx.org/advanced/#pool-limit-configuration
            # instruct the remote uvicorn web server to close the connections
            # https://www.uvicorn.org/server-behavior/#http-headers
            "headers": {
                "Connection": "Close",
            }
        }
        if base_url:
            client_args["base_url"] = base_url
        if default_http_client_timeout:
            client_args["timeout"] = default_http_client_timeout

        client = AsyncClient(**client_args)
        if tracing_settings:
            setup_httpx_client_tracing(client)
        super().__init__(client=client)

    async def __aenter__(self):
        await self.setup_client()
        return self

    async def __aexit__(self, *args):
        _log_pool_status(self.client, "before close")
        await self.teardown_client()
