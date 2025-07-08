import asyncio
import datetime
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from common_library.async_tools import cancel_wait_task
from faker import Faker
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import JobMissingError
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import TypeAdapter
from servicelib.rabbitmq import RabbitMQRPCClient, RemoteMethodNotRegisteredError
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import (
    list_jobs,
    submit,
    submit_and_wait,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def method_name(faker: Faker) -> RPCMethodName:
    return TypeAdapter(RPCMethodName).validate_python(faker.word())


@pytest.fixture
def job_id_data(faker: Faker) -> AsyncJobFilter:
    return AsyncJobFilter(
        user_id=faker.pyint(min_value=1),
        product_name=faker.word(),
    )


@pytest.fixture
def job_id(faker: Faker) -> AsyncJobId:
    return faker.uuid4(cast_to=None)


@pytest.fixture
async def async_job_rpc_server(  # noqa: C901
    rpc_server: RabbitMQRPCClient,
    faker: Faker,
    namespace: RPCNamespace,
    method_name: RPCMethodName,
) -> AsyncIterator[None]:
    async def _slow_task() -> None:
        await asyncio.sleep(2)

    @dataclass
    class FakeServer:
        tasks: list[asyncio.Task] = field(default_factory=list)

        def _get_task(self, job_id: AsyncJobId) -> asyncio.Task:
            for task in self.tasks:
                if task.get_name() == f"{job_id}":
                    return task
            raise JobMissingError(job_id=f"{job_id}")

        async def status(
            self, job_id: AsyncJobId, job_id_data: AsyncJobFilter
        ) -> AsyncJobStatus:
            assert job_id_data
            task = self._get_task(job_id)
            return AsyncJobStatus(
                job_id=job_id,
                progress=ProgressReport(actual_value=1 if task.done() else 0.3),
                done=task.done(),
            )

        async def cancel(self, job_id: AsyncJobId, job_id_data: AsyncJobFilter) -> None:
            assert job_id
            assert job_id_data
            task = self._get_task(job_id)
            task.cancel()

        async def result(
            self, job_id: AsyncJobId, job_id_data: AsyncJobFilter
        ) -> AsyncJobResult:
            assert job_id_data
            task = self._get_task(job_id)
            assert task.done()
            return AsyncJobResult(
                result={
                    "data": task.result(),
                    "job_id": job_id,
                    "job_id_data": job_id_data,
                }
            )

        async def list_jobs(
            self, filter_: str, job_id_data: AsyncJobFilter
        ) -> list[AsyncJobGet]:
            assert job_id_data
            assert filter_ is not None

            return [
                AsyncJobGet(
                    job_id=TypeAdapter(AsyncJobId).validate_python(t.get_name()),
                    job_name="fake_job_name",
                )
                for t in self.tasks
            ]

        async def submit(self, job_id_data: AsyncJobFilter) -> AsyncJobGet:
            assert job_id_data
            job_id = faker.uuid4(cast_to=None)
            self.tasks.append(asyncio.create_task(_slow_task(), name=f"{job_id}"))
            return AsyncJobGet(job_id=job_id, job_name="fake_job_name")

        async def setup(self) -> None:
            for m in (self.status, self.cancel, self.result):
                await rpc_server.register_handler(
                    namespace, RPCMethodName(m.__name__), m
                )
            await rpc_server.register_handler(
                namespace, RPCMethodName(self.list_jobs.__name__), self.list_jobs
            )

            await rpc_server.register_handler(namespace, method_name, self.submit)

    fake_server = FakeServer()
    await fake_server.setup()

    yield

    for task in fake_server.tasks:
        await cancel_wait_task(task)


@pytest.mark.parametrize("method", ["result", "status", "cancel"])
async def test_async_jobs_methods(
    async_job_rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    namespace: RPCNamespace,
    job_id_data: AsyncJobFilter,
    job_id: AsyncJobId,
    method: str,
):
    from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs

    async_jobs_method = getattr(async_jobs, method)
    with pytest.raises(JobMissingError):
        await async_jobs_method(
            rpc_client,
            rpc_namespace=namespace,
            job_id=job_id,
            job_id_data=job_id_data,
        )


async def test_list_jobs(
    async_job_rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    namespace: RPCNamespace,
    method_name: RPCMethodName,
    job_id_data: AsyncJobFilter,
):
    await list_jobs(
        rpc_client,
        rpc_namespace=namespace,
        filter_="",
        job_filter=job_id_data,
    )


async def test_submit(
    async_job_rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    namespace: RPCNamespace,
    method_name: RPCMethodName,
    job_id_data: AsyncJobFilter,
):
    await submit(
        rpc_client,
        rpc_namespace=namespace,
        method_name=method_name,
        job_filter=job_id_data,
    )


async def test_submit_with_invalid_method_name(
    async_job_rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    namespace: RPCNamespace,
    job_id_data: AsyncJobFilter,
):
    with pytest.raises(RemoteMethodNotRegisteredError):
        await submit(
            rpc_client,
            rpc_namespace=namespace,
            method_name=RPCMethodName("invalid_method_name"),
            job_filter=job_id_data,
        )


async def test_submit_and_wait_properly_timesout(
    async_job_rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    namespace: RPCNamespace,
    method_name: RPCMethodName,
    job_id_data: AsyncJobFilter,
):
    with pytest.raises(TimeoutError):  # noqa: PT012
        async for _job_composed_result in submit_and_wait(
            rpc_client,
            rpc_namespace=namespace,
            method_name=method_name,
            job_filter=job_id_data,
            client_timeout=datetime.timedelta(seconds=0.1),
        ):
            pass


async def test_submit_and_wait(
    async_job_rpc_server: RabbitMQRPCClient,
    rpc_client: RabbitMQRPCClient,
    namespace: RPCNamespace,
    method_name: RPCMethodName,
    job_id_data: AsyncJobFilter,
):
    async for job_composed_result in submit_and_wait(
        rpc_client,
        rpc_namespace=namespace,
        method_name=method_name,
        job_filter=job_id_data,
        client_timeout=datetime.timedelta(seconds=10),
    ):
        if not job_composed_result.done:
            with pytest.raises(ValueError, match="No result ready!"):
                await job_composed_result.result()
    assert job_composed_result.done
    assert job_composed_result.status.progress.actual_value == 1
    assert await job_composed_result.result() == AsyncJobResult(
        result={
            "data": None,
            "job_id": job_composed_result.status.job_id,
            "job_id_data": job_id_data,
        }
    )
