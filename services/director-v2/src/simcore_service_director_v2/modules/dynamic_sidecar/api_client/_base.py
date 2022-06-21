import asyncio
import functools
import inspect
import logging
from logging import Logger
from typing import Any, Awaitable, Callable, Optional

from httpx import AsyncClient, ConnectError, Response, TransportError
from httpx._types import TimeoutTypes, URLTypes
from tenacity import RetryCallState
from tenacity._asyncio import AsyncRetrying
from tenacity.before import before_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

from ._errors import (
    ClientTransportError,
    UnexpectedStatusError,
    WrongReturnType,
    _RetryRequestError,
)

logger = logging.getLogger(__name__)


def _log_retry(log: Logger, max_retries: int) -> Callable[[RetryCallState], None]:
    def log_it(retry_state: RetryCallState) -> None:
        # pylint: disable=protected-access

        assert retry_state.outcome  # nosec
        e = retry_state.outcome.exception()
        assert e.error  # nosec
        assert e.error._request  # nosec

        log.info(
            "[%s/%s]Retry. Unexpected ConnectError while requesting '%s %s': %s",
            retry_state.attempt_number,
            max_retries,
            e.error._request.method,
            e.error._request.url,
            f"{e=}",
        )

    return log_it


def retry_on_errors(
    request_func: Callable[..., Awaitable[Response]]
) -> Callable[..., Awaitable[Response]]:
    """
    raises:
    - `ClientTransportError`
    - `httpx.HTTPError`
    """
    assert asyncio.iscoroutinefunction(request_func)

    @functools.wraps(request_func)
    async def request_wrapper(zelf: "BaseThinClient", *args, **kwargs) -> Response:
        # pylint: disable=protected-access
        try:
            async for attempt in AsyncRetrying(
                # waits 1, 4, 8 seconds between retries and gives up
                stop=stop_after_attempt(zelf._request_max_retries),
                wait=wait_exponential(min=1),
                retry=retry_if_exception_type(_RetryRequestError),
                before=before_log(logger, logging.DEBUG),
                after=_log_retry(logger, zelf._request_max_retries),
                reraise=True,
            ):
                with attempt:
                    try:
                        response: Response = await request_func(zelf, *args, **kwargs)
                        return response
                    except ConnectError as e:
                        assert e._request
                        raise _RetryRequestError(e) from e
                    except TransportError as e:
                        raise ClientTransportError from e
        except _RetryRequestError as e:
            # raise original exception
            assert e.__cause__  # nosec
            raise e.__cause__

    return request_wrapper


def expect_status(expected_code: int):
    """
    NOTE: always apply after `retry_on_errors`

    raises:
    - `UnexpectedStatusError`
    - `httpx.HTTPError`
    """

    def decorator(
        request_func: Callable[..., Awaitable[Response]]
    ) -> Callable[..., Awaitable[Response]]:
        assert asyncio.iscoroutinefunction(request_func)

        @functools.wraps(request_func)
        async def request_wrapper(zelf: "BaseThinClient", *args, **kwargs) -> Response:
            logger.debug("Calling expect_status")

            response = await request_func(zelf, *args, **kwargs)
            if response.status_code != expected_code:
                raise UnexpectedStatusError(response, expected_code)

            return response

        return request_wrapper

    return decorator


class BaseThinClient:
    SKIP_METHODS: set[str] = {"close"}

    def __init__(
        self,
        *,
        request_max_retries: int,
        base_url: Optional[URLTypes] = None,
        timeout: Optional[TimeoutTypes] = None,
    ) -> None:
        self._request_max_retries: int = request_max_retries

        client_args: dict[str, Any] = {}
        if base_url:
            client_args["base_url"] = base_url
        if timeout:
            client_args["timeout"] = timeout
        self._client = AsyncClient(**client_args)

        # ensure all user defined public methods return `httpx.Response``

        public_methods = [
            t[1]
            for t in inspect.getmembers(self, predicate=inspect.ismethod)
            if not (t[0].startswith("_") or t[0] in self.SKIP_METHODS)
        ]

        for method in public_methods:
            signature = inspect.signature(method)
            if signature.return_annotation != Response:
                raise WrongReturnType(method, signature.return_annotation)

    async def close(self) -> None:
        # pylint: disable=protected-access
        logger.warning(
            "REQUESTS WHILE CLOSING %s",
            [
                (r.request.method, r.request.url, r.request.headers)
                for r in self._client._transport._pool._requests
            ],
        )
        await self._client.aclose()
