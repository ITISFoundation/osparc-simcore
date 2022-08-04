import asyncio
import functools
import logging
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, status
from httpx import AsyncClient, HTTPError
from pydantic import AnyHttpUrl, PositiveFloat, parse_obj_as
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

from ._errors import GenericClientError, TaskClientResultError
from ._models import ClientConfiguration, TaskId, TaskResult, TaskStatus

logger = logging.getLevelName(__name__)


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
            reraise=True,
        ):
            with attempt:
                return await request_func(zelf, *args, **kwargs)

    return request_wrapper


class Client:
    """
    This is a client that aims to simplify the requests to get the
    status, result and/or cancel of a long running task.
    """

    def __init__(self, app: FastAPI, async_client: AsyncClient, base_url: AnyHttpUrl):
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
        return self.app.state.long_running_client_configuration

    def _get_url(self, path: str) -> AnyHttpUrl:
        return parse_obj_as(
            AnyHttpUrl,
            f"{self._base_url}{self._client_configuration.router_prefix}{path}",
        )

    @retry_on_http_errors
    async def get_task_status(
        self, task_id: TaskId, *, timeout: Optional[PositiveFloat] = None
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

        return TaskStatus.parse_obj(result.json())

    @retry_on_http_errors
    async def get_task_result(
        self, task_id: TaskId, *, timeout: Optional[PositiveFloat] = None
    ) -> Optional[Any]:
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

        task_result = TaskResult.parse_obj(result.json())
        if task_result.error is not None:
            raise TaskClientResultError(message=task_result.error)
        return task_result.result

    @retry_on_http_errors
    async def cancel_and_delete_task(
        self, task_id: TaskId, *, timeout: Optional[PositiveFloat] = None
    ) -> bool:
        timeout = timeout or self._client_configuration.default_timeout
        result = await self._async_client.delete(
            self._get_url(f"/task/{task_id}"),
            timeout=timeout,
        )
        if result.status_code != status.HTTP_200_OK:
            raise GenericClientError(
                action="cancelling_and_removing_task",
                task_id=task_id,
                status=result.status_code,
                body=result.text,
            )
        return result.json()


def setup(
    app: FastAPI,
    *,
    router_prefix: str = "",
    http_requests_timeout: PositiveFloat = 15,
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
