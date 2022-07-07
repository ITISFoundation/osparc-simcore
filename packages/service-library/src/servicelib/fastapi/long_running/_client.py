from functools import cached_property
from typing import Any, Optional

from fastapi import FastAPI, status
from httpx import AsyncClient, Timeout
from pydantic import AnyHttpUrl

from ._errors import TaskClientResultErrorError
from ._models import TaskId, TaskStatus


# change like the other PR with the same model to fetch the properties
class Client:
    def __init__(
        self,
        *,
        prefix: str,
        timeout: float,
        status_poll_interval: float,
    ) -> None:
        self._timeout = Timeout(timeout)
        self._prefix = prefix
        self._status_poll_interval = status_poll_interval

    @cached_property
    def status_poll_interval(self) -> float:
        return self._status_poll_interval

    def _get_url(self, base_url: AnyHttpUrl, path: str) -> str:
        return f"{base_url}{self._prefix}{path}"

    async def get_task_status(
        self, async_client: AsyncClient, base_url: AnyHttpUrl, task_id: TaskId
    ) -> TaskStatus:
        result = await async_client.get(
            self._get_url(base_url, f"/task/{task_id}"), timeout=self._timeout
        )
        assert result.status_code == status.HTTP_200_OK  # nosec
        return TaskStatus.parse_obj(result.json())

    async def get_task_result(
        self, async_client: AsyncClient, base_url: AnyHttpUrl, task_id: TaskId
    ) -> Optional[Any]:
        result = await async_client.get(
            self._get_url(base_url, f"/task/{task_id}/result"), timeout=self._timeout
        )
        if result.status_code == status.HTTP_200_OK:
            return result.json()
        if result.status_code == status.HTTP_400_BAD_REQUEST:
            raise TaskClientResultErrorError(task_id=task_id, message=result.json())

    async def cancel_and_delete_task(
        self, async_client: AsyncClient, base_url: AnyHttpUrl, task_id: TaskId
    ) -> None:
        result = await async_client.delete(
            self._get_url(base_url, f"/task/{task_id}"), timeout=self._timeout
        )
        assert result.status_code == status.HTTP_200_OK  # nosec


def setup(
    app: FastAPI,
    *,
    router_prefix: str = "",
    http_requests_timeout: float = 15,
    status_poll_interval: float = 5,
):
    async def on_startup() -> None:
        app.state.long_running_client = Client(
            prefix=router_prefix,
            timeout=http_requests_timeout,
            status_poll_interval=status_poll_interval,
        )

    async def on_shutdown() -> None:
        app.state.long_running_client = None

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
