# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from asyncio import Task
from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Any

import pytest
from servicelib.async_utils import cancel_wait_task
from servicelib.background_task import create_periodic_task
from servicelib.long_running_interfaces._errors import (
    JobNotFoundError,
    NoResultIsAvailableError,
)
from servicelib.long_running_interfaces._models import (
    JobName,
    JobStatus,
    JobUniqueId,
    LongRunningNamespace,
    ResultModel,
    StartParams,
)
from servicelib.long_running_interfaces._rpc.client import ClientRPCInterface
from servicelib.long_running_interfaces._rpc.server import (
    BaseServerJobInterface,
    ServerRPCInterface,
)
from settings_library.rabbit import RabbitSettings
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
async def client_rpc_interface(
    rabbit_service: RabbitSettings, long_running_namespace: LongRunningNamespace
) -> AsyncIterable[ClientRPCInterface]:
    client = ClientRPCInterface(rabbit_service, long_running_namespace)
    await client.setup()
    yield client
    await client.teardown()


class MockServerInterface(BaseServerJobInterface):
    def __init__(self) -> None:
        self._storage: dict[JobUniqueId, Any] = {}

        self._task: Task | None = None

    async def _worker(self) -> None:
        # decreates duration for each task
        for unique_id in set(self._storage.keys()):
            if entry := self._storage.get(unique_id, None):
                entry["time_remaining"] -= 1

    async def setup(self) -> None:
        self._task = create_periodic_task(
            self._worker,
            interval=timedelta(seconds=1),
            task_name="mock_worker",
            raise_on_error=True,
        )

    async def teardown(self) -> None:
        if self._task:
            await cancel_wait_task(self._task, max_delay=5)

    def _get_from_storage(self, unique_id: JobUniqueId) -> dict:
        if unique_id not in self._storage:
            msg = "job {unique_id} not found"
            raise RuntimeError(msg)
        return self._storage[unique_id]

    async def start(self, unique_id: JobUniqueId, **params: StartParams) -> None:
        self._storage[unique_id] = {"params": params, "time_remaining": 5}

    async def remove(self, unique_id: JobUniqueId) -> None:
        del self._storage[unique_id]

    async def is_present(self, unique_id: JobName) -> bool:
        return unique_id in self._storage

    async def is_running(self, unique_id: JobName) -> bool:
        if unique_id not in self._storage:
            return False
        data = self._get_from_storage(unique_id)
        is_running: bool = data.get("time_remaining", 0) > 0
        return is_running

    async def get_result(self, unique_id: JobUniqueId) -> ResultModel:
        if await self.is_running(unique_id):
            raise RuntimeError("still not finished")

        # TODO: also emulate errors
        return ResultModel(data="done")


@pytest.fixture
async def initilized_server_interface() -> AsyncIterable[MockServerInterface]:
    interface = MockServerInterface()
    await interface.setup()
    yield interface
    await interface.teardown()


@pytest.fixture
async def server_rpc_interface(
    rabbit_service: RabbitSettings,
    long_running_namespace: LongRunningNamespace,
    initilized_server_interface: MockServerInterface,
) -> AsyncIterable[ServerRPCInterface]:
    server = ServerRPCInterface(
        rabbit_service, long_running_namespace, initilized_server_interface
    )
    await server.setup()
    yield server
    await server.teardown()


async def test_workflow(
    server_rpc_interface: ServerRPCInterface,
    client_rpc_interface: ClientRPCInterface,
    unique_id: JobUniqueId,
    job_timeout: timedelta,
) -> None:

    # not started yet
    assert await client_rpc_interface.get_status(unique_id) == JobStatus.NOT_FOUND
    with pytest.raises(JobNotFoundError):
        assert await client_rpc_interface.get_result(unique_id)

    # after start
    await client_rpc_interface.start(unique_id, timeout=job_timeout)

    assert await client_rpc_interface.get_status(unique_id) == JobStatus.RUNNING
    with pytest.raises(NoResultIsAvailableError):
        assert await client_rpc_interface.get_result(unique_id)

    # wait to be finsiehd
    async for attempt in AsyncRetrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert (
                await client_rpc_interface.get_status(unique_id) == JobStatus.FINISHED
            )

    # finally the result
    assert await client_rpc_interface.get_result(unique_id) == ResultModel(data="done")


# TODO: we need to figure out how to deal with errors and unexpected errors, how do we pass those on via the result interface?
