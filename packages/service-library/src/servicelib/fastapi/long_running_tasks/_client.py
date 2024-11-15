import asyncio
import functools
import logging
import warnings
from typing import Any, Awaitable, Callable, Final

from fastapi import FastAPI, status
from httpx import AsyncClient, HTTPError
from pydantic import AnyHttpUrl, PositiveFloat, TypeAdapter
from tenacity import RetryCallState
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

from ...long_running_tasks._errors import GenericClientError, TaskClientResultError
from ...long_running_tasks._models import (
    ClientConfiguration,
    TaskId,
    TaskResult,
    TaskStatus,
)

DEFAULT_HTTP_REQUESTS_TIMEOUT: Final[PositiveFloat] = 15


logger = logging.getLogger(__name__)


def _before_sleep_log(
    request_function: Callable[..., Awaitable[Any]],
    args: Any,
    kwargs: dict[str, Any],
    *,
    exc_info: bool = False,
) -> Callable[[RetryCallState], None]:
    """Before call strategy that logs to some logger the attempt."""

    def log_it(retry_state: "RetryCallState") -> None:
        assert retry_state.outcome  # nosec
        if retry_state.outcome.failed:
            ex = retry_state.outcome.exception()
            verb, value = "raised", f"{ex.__class__.__name__}: {ex}"
            local_exc_info = exc_info
        else:
            verb, value = "returned", retry_state.outcome.result()
            local_exc_info = False  # exc_info does not apply when no exception

        assert retry_state.next_action  # nosec
        logger.warning(
            "Retrying '%s %s %s' in %s seconds as it %s %s. %s",
            request_function.__name__,
            f"{args=}",
            f"{kwargs=}",
            retry_state.next_action.sleep,
            verb,
            value,
            retry_state.retry_object.statistics,
            exc_info=local_exc_info,
        )

    return log_it


def _after_log(
    request_function: Callable[..., Awaitable[Any]],
    args: Any,
    kwargs: dict[str, Any],
    *,
    sec_format: str = "%0.3f",
) -> Callable[[RetryCallState], None]:
    """After call strategy that logs to some logger the finished attempt."""

    def log_it(retry_state: RetryCallState) -> None:
        logger.error(
            "Failed call to '%s %s %s' after %s(s), this was the %s time calling it.",
            request_function.__name__,
            f"{args=}",
            f"{kwargs=}",
            sec_format % retry_state.seconds_since_start,
            retry_state.attempt_number,
        )

    return log_it


def retry_on_http_errors(
    request_func: Callable[..., Awaitable[Any]]
) -> Callable[..., Awaitable[Any]]:
    """
    Will retry the request on `httpx.HTTPError`.
    """
    assert asyncio.iscoroutinefunction(request_func)

    @functools.wraps(request_func)
    async def request_wrapper(zelf: "Client", *args, **kwargs) -> Any:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempt_number=3),
            wait=wait_exponential(min=1),
            retry=retry_if_exception_type(HTTPError),
            before_sleep=_before_sleep_log(request_func, args, kwargs),
            after=_after_log(request_func, args, kwargs),
            reraise=True,
        ):
            with attempt:
                return await request_func(zelf, *args, **kwargs)

        msg = "Unexpected"
        raise RuntimeError(msg)

    return request_wrapper


class Client:
    """
    This is a client that aims to simplify the requests to get the
    status, result and/or cancel of a long running task.
    """

    def __init__(self, app: FastAPI, async_client: AsyncClient, base_url: str):
        """
        `app`: used byt the `Client` to recover the `ClientConfiguration`
        `async_client`: an AsyncClient instance used by `Client`
        `base_url`: base endpoint where the server is listening on
        """
        self.app = app
        self._async_client = async_client
        self._base_url = base_url

    @property
    def _client_configuration(self) -> ClientConfiguration:
        output: ClientConfiguration = self.app.state.long_running_client_configuration
        return output

    def _get_url(self, path: str) -> str:
        url_path = f"{self._client_configuration.router_prefix}{path}".lstrip("/")
        url = TypeAdapter(AnyHttpUrl).validate_python(f"{self._base_url}{url_path}")
        return f"{url}"

    @retry_on_http_errors
    async def get_task_status(
        self, task_id: TaskId, *, timeout: PositiveFloat | None = None  # noqa: ASYNC109
    ) -> TaskStatus:
        timeout = timeout or self._client_configuration.default_timeout
        result = await self._async_client.get(
            self._get_url(f"/task/{task_id}"),
            timeout=timeout,
        )
        if result.status_code != status.HTTP_200_OK:
            raise GenericClientError(
                action="getting_status",
                task_id=task_id,
                status=result.status_code,
                body=result.text,
            )

        return TaskStatus.model_validate(result.json())

    @retry_on_http_errors
    async def get_task_result(
        self, task_id: TaskId, *, timeout: PositiveFloat | None = None  # noqa: ASYNC109
    ) -> Any | None:
        timeout = timeout or self._client_configuration.default_timeout
        result = await self._async_client.get(
            self._get_url(f"/task/{task_id}/result"),
            timeout=timeout,
        )
        if result.status_code != status.HTTP_200_OK:
            raise GenericClientError(
                action="getting_result",
                task_id=task_id,
                status=result.status_code,
                body=result.text,
            )

        task_result = TaskResult.model_validate(result.json())
        if task_result.error is not None:
            raise TaskClientResultError(message=task_result.error)
        return task_result.result

    @retry_on_http_errors
    async def cancel_and_delete_task(
        self, task_id: TaskId, *, timeout: PositiveFloat | None = None  # noqa: ASYNC109
    ) -> None:
        timeout = timeout or self._client_configuration.default_timeout
        result = await self._async_client.delete(
            self._get_url(f"/task/{task_id}"),
            timeout=timeout,
        )

        if result.status_code == status.HTTP_200_OK:
            warnings.warn(
                "returning a 200 when cancelling a task has been deprecated with PR#3236"
                "and will be removed after 11.2022"
                "please do close your studies at least once before that date, so that the dy-sidecar"
                "get replaced",
                category=DeprecationWarning,
            )
            return

        if result.status_code not in (
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
        ):
            raise GenericClientError(
                action="cancelling_and_removing_task",
                task_id=task_id,
                status=result.status_code,
                body=result.text,
            )


def setup(
    app: FastAPI,
    *,
    router_prefix: str = "",
    http_requests_timeout: PositiveFloat = DEFAULT_HTTP_REQUESTS_TIMEOUT,
):
    """
    - `router_prefix` by default it is assumed the server mounts the APIs on
        `/task/...` this will assume the APIs are as following
        `{router_prefix}/task/...`
    - `http_requests_timeout` short requests are used to interact with the
        server API, a low timeout is sufficient
    """

    async def on_startup() -> None:
        app.state.long_running_client_configuration = ClientConfiguration(
            router_prefix=router_prefix, default_timeout=http_requests_timeout
        )

    app.add_event_handler("startup", on_startup)
