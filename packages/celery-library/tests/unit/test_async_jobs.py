# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import pickle
from collections.abc import Callable
from datetime import timedelta
from enum import Enum
from typing import Any, Final

import pytest
from celery import Celery, Task
from celery.contrib.testing.worker import TestWorkController
from celery_library.rpc import _async_jobs
from celery_library.task import register_task
from common_library.errors_classes import OsparcErrorMixin
from faker import Faker
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCNamespace
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.celery.models import TaskID, TaskMetadata
from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RabbitMQRPCClient, RPCRouter
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


class AccessRightError(OsparcErrorMixin, RuntimeError):
    msg_template: str = (
        "User {user_id} does not have access to file {file_id} with location {location_id}"
    )


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def product_name(faker: Faker) -> ProductName:
    return faker.word()


###### RPC Interface ######
router = RPCRouter()

ASYNC_JOBS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    RPCNamespace
).validate_python("async_jobs")


@router.expose()
async def rpc_sync_job(
    task_manager: TaskManager, *, job_id_data: AsyncJobNameData, **kwargs: Any
) -> AsyncJobGet:
    task_name = sync_job.__name__
    task_uuid = await task_manager.submit_task(
        TaskMetadata(name=task_name), task_context=job_id_data.model_dump(), **kwargs
    )

    return AsyncJobGet(job_id=task_uuid, job_name=task_name)


@router.expose()
async def rpc_async_job(
    task_manager: TaskManager, *, job_id_data: AsyncJobNameData, **kwargs: Any
) -> AsyncJobGet:
    task_name = async_job.__name__
    task_uuid = await task_manager.submit_task(
        TaskMetadata(name=task_name), task_context=job_id_data.model_dump(), **kwargs
    )

    return AsyncJobGet(job_id=task_uuid, job_name=task_name)


#################################


###### CELERY TASKS ######
class Action(str, Enum):
    ECHO = "ECHO"
    RAISE = "RAISE"
    SLEEP = "SLEEP"


async def _process_action(action: str, payload: Any) -> Any:
    match action:
        case Action.ECHO:
            return payload
        case Action.RAISE:
            raise pickle.loads(payload)  # noqa: S301
        case Action.SLEEP:
            await asyncio.sleep(payload)
    return None


def sync_job(task: Task, task_id: TaskID, action: Action, payload: Any) -> Any:
    _ = task
    _ = task_id
    return asyncio.run(_process_action(action, payload))


async def async_job(task: Task, task_id: TaskID, action: Action, payload: Any) -> Any:
    _ = task
    _ = task_id
    return await _process_action(action, payload)


#################################


@pytest.fixture
async def register_rpc_routes(
    async_jobs_rabbitmq_rpc_client: RabbitMQRPCClient, celery_task_manager: TaskManager
) -> None:
    await async_jobs_rabbitmq_rpc_client.register_router(
        _async_jobs.router, ASYNC_JOBS_RPC_NAMESPACE, task_manager=celery_task_manager
    )
    await async_jobs_rabbitmq_rpc_client.register_router(
        router, ASYNC_JOBS_RPC_NAMESPACE, task_manager=celery_task_manager
    )


async def _start_task_via_rpc(
    client: RabbitMQRPCClient,
    *,
    rpc_task_name: str,
    user_id: UserID,
    product_name: ProductName,
    **kwargs: Any,
) -> tuple[AsyncJobGet, AsyncJobNameData]:
    job_id_data = AsyncJobNameData(user_id=user_id, product_name=product_name)
    async_job_get = await async_jobs.submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
        method_name=rpc_task_name,
        job_id_data=job_id_data,
        **kwargs,
    )
    return async_job_get, job_id_data


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        register_task(
            celery_app,
            sync_job,
            max_retries=1,
            delay_between_retries=timedelta(seconds=1),
            dont_autoretry_for=(AccessRightError,),
        )
        register_task(
            celery_app,
            async_job,
            max_retries=1,
            delay_between_retries=timedelta(seconds=1),
            dont_autoretry_for=(AccessRightError,),
        )

    return _


async def _wait_for_job(
    rpc_client: RabbitMQRPCClient,
    *,
    async_job_get: AsyncJobGet,
    job_id_data: AsyncJobNameData,
    stop_after: timedelta = timedelta(seconds=5),
) -> None:

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(stop_after.total_seconds()),
        wait=wait_fixed(0.1),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            result = await async_jobs.status(
                rpc_client,
                rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
                job_id=async_job_get.job_id,
                job_id_data=job_id_data,
            )
            assert (
                result.done is True
            ), "Please check logs above, something whent wrong with task execution"


@pytest.mark.parametrize(
    "exposed_rpc_start",
    [
        rpc_sync_job.__name__,
        rpc_async_job.__name__,
    ],
)
@pytest.mark.parametrize(
    "payload",
    [
        None,
        1,
        "a_string",
        {"a": "dict"},
        ["a", "list"],
        {"a", "set"},
    ],
)
async def test_async_jobs_workflow(
    register_rpc_routes: None,
    async_jobs_rabbitmq_rpc_client: RabbitMQRPCClient,
    with_celery_worker: TestWorkController,
    user_id: UserID,
    product_name: ProductName,
    exposed_rpc_start: str,
    payload: Any,
):
    async_job_get, job_id_data = await _start_task_via_rpc(
        async_jobs_rabbitmq_rpc_client,
        rpc_task_name=exposed_rpc_start,
        user_id=user_id,
        product_name=product_name,
        action=Action.ECHO,
        payload=payload,
    )

    jobs = await async_jobs.list_jobs(
        async_jobs_rabbitmq_rpc_client,
        rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
        filter_="",  # currently not used
        job_id_data=job_id_data,
    )
    assert len(jobs) > 0

    await _wait_for_job(
        async_jobs_rabbitmq_rpc_client,
        async_job_get=async_job_get,
        job_id_data=job_id_data,
    )

    async_job_result = await async_jobs.result(
        async_jobs_rabbitmq_rpc_client,
        rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
        job_id=async_job_get.job_id,
        job_id_data=job_id_data,
    )
    assert async_job_result.result == payload


@pytest.mark.parametrize(
    "exposed_rpc_start",
    [
        rpc_async_job.__name__,
    ],
)
async def test_async_jobs_cancel(
    register_rpc_routes: None,
    async_jobs_rabbitmq_rpc_client: RabbitMQRPCClient,
    with_celery_worker: TestWorkController,
    user_id: UserID,
    product_name: ProductName,
    exposed_rpc_start: str,
):
    async_job_get, job_id_data = await _start_task_via_rpc(
        async_jobs_rabbitmq_rpc_client,
        rpc_task_name=exposed_rpc_start,
        user_id=user_id,
        product_name=product_name,
        action=Action.SLEEP,
        payload=60 * 10,  # test hangs if not cancelled properly
    )

    await async_jobs.cancel(
        async_jobs_rabbitmq_rpc_client,
        rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
        job_id=async_job_get.job_id,
        job_id_data=job_id_data,
    )

    await _wait_for_job(
        async_jobs_rabbitmq_rpc_client,
        async_job_get=async_job_get,
        job_id_data=job_id_data,
    )

    jobs = await async_jobs.list_jobs(
        async_jobs_rabbitmq_rpc_client,
        rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
        filter_="",  # currently not used
        job_id_data=job_id_data,
    )
    assert async_job_get.job_id not in [job.job_id for job in jobs]

    with pytest.raises(JobAbortedError):
        await async_jobs.result(
            async_jobs_rabbitmq_rpc_client,
            rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
            job_id=async_job_get.job_id,
            job_id_data=job_id_data,
        )


@pytest.mark.parametrize(
    "exposed_rpc_start",
    [
        rpc_sync_job.__name__,
        rpc_async_job.__name__,
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(Exception("generic error"), id="generic-error"),
        pytest.param(
            AccessRightError(user_id=1, file_id="fake_key", location_id=0),
            id="custom-osparc-error",
        ),
    ],
)
async def test_async_jobs_raises(
    register_rpc_routes: None,
    async_jobs_rabbitmq_rpc_client: RabbitMQRPCClient,
    with_celery_worker: TestWorkController,
    user_id: UserID,
    product_name: ProductName,
    exposed_rpc_start: str,
    error: Exception,
):
    async_job_get, job_id_data = await _start_task_via_rpc(
        async_jobs_rabbitmq_rpc_client,
        rpc_task_name=exposed_rpc_start,
        user_id=user_id,
        product_name=product_name,
        action=Action.RAISE,
        payload=pickle.dumps(error),
    )

    await _wait_for_job(
        async_jobs_rabbitmq_rpc_client,
        async_job_get=async_job_get,
        job_id_data=job_id_data,
        stop_after=timedelta(minutes=1),
    )

    with pytest.raises(JobError) as exc:
        await async_jobs.result(
            async_jobs_rabbitmq_rpc_client,
            rpc_namespace=ASYNC_JOBS_RPC_NAMESPACE,
            job_id=async_job_get.job_id,
            job_id_data=job_id_data,
        )
    assert exc.value.exc_type == type(error).__name__
    assert exc.value.exc_msg == f"{error}"
