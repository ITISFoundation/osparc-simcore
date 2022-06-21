import asyncio
import functools
import inspect
import logging
from typing import Any, Awaitable, Callable, Optional

from httpx import AsyncClient, ConnectError, Response, TransportError
from httpx._types import TimeoutTypes, URLTypes
from tenacity._asyncio import AsyncRetrying
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
    async def request_wrapper(zelf: "BaseHThinClient", *args, **kwargs) -> Response:
        # pylint:disable=protected-access
        try:
            async for attempt in AsyncRetrying(
                # waits 1, 4, 8 seconds between retries and gives up
                stop=stop_after_attempt(zelf._request_max_retries),
                wait=wait_exponential(min=1),
                retry=retry_if_exception_type(_RetryRequestError),
                reraise=True,
            ):
                with attempt:
                    try:
                        logger.debug("Calling retry_on_errors")
                        response: Response = await request_func(zelf, *args, **kwargs)
                        return response
                    except ConnectError as e:
                        assert e._request
                        logger.info(
                            "[%s/%s]Retry. Unexpected ConnectError while requesting '%s %s': %s",
                            attempt.retry_state.attempt_number,
                            zelf._request_max_retries,
                            e._request.method,
                            e._request.url,
                            f"{e=}",
                        )
                        raise _RetryRequestError(e) from e
                    except TransportError as e:
                        raise ClientTransportError from e
        except _RetryRequestError as e:
            # raise original exception
            assert e.__cause__
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
        async def request_wrapper(zelf: "BaseHThinClient", *args, **kwargs) -> Response:
            logger.debug("Calling expect_status")

            response = await request_func(zelf, *args, **kwargs)
            if response.status_code != expected_code:
                raise UnexpectedStatusError(response, expected_code)

            return response

        return request_wrapper

    return decorator


class BaseHThinClient:
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
        self._client: AsyncClient = AsyncClient(**client_args)

        # ensure all user defined public methods return `httpx.Response``

        pubic_methods = [
            x
            for x in inspect.getmembers(self, predicate=inspect.ismethod)
            if not (x[0].startswith("_") or x[0] in self.SKIP_METHODS)
        ]

        for _, method in pubic_methods:
            signature = inspect.signature(method)
            if signature.return_annotation != Response:
                raise WrongReturnType(method, signature.return_annotation)

    async def close(self) -> None:
        # pylint: disable=protected-access
        logger.debug(
            "REQUESTS WHILE CLOSING %s",
            [
                (r.request.method, r.request.url, r.request.headers)
                for r in self._client._transport._pool._requests
            ],
        )
        await self._client.aclose()
