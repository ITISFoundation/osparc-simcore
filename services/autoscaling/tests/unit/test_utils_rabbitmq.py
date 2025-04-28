# pylint: disable=too-many-positional-arguments
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import aiodocker
import pytest
from dask_task_models_library.container_tasks.utils import generate_dask_job_id
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerLabelKey, StandardSimcoreDockerLabels
from models_library.generated_models.docker_rest_api import Service, Task
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressType,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.models import DaskTask
from simcore_service_autoscaling.utils.rabbitmq import (
    post_tasks_log_message,
    post_tasks_progress_message,
)
from tenacity import RetryError, retry_always
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_TENACITY_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(30),
    "wait": wait_fixed(0.1),
}

_TENACITY_STABLE_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_always,
    "stop": stop_after_delay(3),
    "wait": wait_fixed(1),
}


# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
async def logs_rabbitmq_consumer(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocker: MockerFixture,
) -> AsyncMock:
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    client = create_rabbitmq_client("pytest_consumer")
    await client.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS],
    )
    return mocked_message_handler


@pytest.fixture
async def progress_rabbitmq_consumer(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocker: MockerFixture,
) -> AsyncMock:
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    client = create_rabbitmq_client("pytest_consumer")
    await client.subscribe(
        ProgressRabbitMessageNode.get_channel_name(),
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS],
    )
    return mocked_message_handler


@pytest.fixture
async def running_service_tasks(
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    async_docker_client: aiodocker.Docker,
) -> Callable[[dict[DockerLabelKey, str]], Awaitable[list[Task]]]:
    async def _(labels: dict[DockerLabelKey, str]) -> list[Task]:
        # Simulate a running service
        service = await create_service(
            task_template,
            labels,
            "running",
        )
        assert service.spec

        docker_tasks = TypeAdapter(list[Task]).validate_python(
            await async_docker_client.tasks.list(filters={"service": service.spec.name})
        )
        assert docker_tasks
        assert len(docker_tasks) == 1
        return docker_tasks

    return _


@pytest.fixture
def service_version() -> ServiceVersion:
    return "1.0.0"


@pytest.fixture
def service_key() -> ServiceKey:
    return "simcore/services/dynamic/test"


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def dask_task(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> DaskTask:
    dask_key = generate_dask_job_id(
        service_key, service_version, user_id, project_id, node_id
    )
    return DaskTask(task_id=dask_key, required_resources={})


@pytest.fixture
def dask_task_with_invalid_key(
    faker: Faker,
) -> DaskTask:
    dask_key = faker.pystr()
    return DaskTask(task_id=dask_key, required_resources={})


async def test_post_task_empty_tasks(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    logs_rabbitmq_consumer: AsyncMock,
    progress_rabbitmq_consumer: AsyncMock,
):
    await post_tasks_log_message(initialized_app, tasks=[], message="no tasks")
    await post_tasks_progress_message(
        initialized_app,
        tasks=[],
        progress=0,
        progress_type=ProgressType.CLUSTER_UP_SCALING,
    )

    with pytest.raises(RetryError):  # noqa: PT012
        async for attempt in AsyncRetrying(**_TENACITY_STABLE_RETRY_PARAMS):
            with attempt:
                print(
                    f"--> checking for message in rabbit exchange {LoggerRabbitMessage.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
                )

                logs_rabbitmq_consumer.assert_not_called()
                progress_rabbitmq_consumer.assert_not_called()
                print("... no message received")


async def test_post_task_log_message_docker(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    running_service_tasks: Callable[[dict[DockerLabelKey, str]], Awaitable[list[Task]]],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
    faker: Faker,
    logs_rabbitmq_consumer: AsyncMock,
):
    docker_tasks = await running_service_tasks(
        osparc_docker_label_keys.to_simcore_runtime_docker_labels()
    )
    assert len(docker_tasks) == 1
    log_message = faker.pystr()
    await post_tasks_log_message(
        initialized_app, tasks=docker_tasks, message=log_message, level=0
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {LoggerRabbitMessage.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
            )
            logs_rabbitmq_consumer.assert_called_once_with(
                LoggerRabbitMessage(
                    node_id=osparc_docker_label_keys.node_id,
                    project_id=osparc_docker_label_keys.project_id,
                    user_id=osparc_docker_label_keys.user_id,
                    messages=[f"[cluster] {log_message}"],
                    log_level=0,
                )
                .model_dump_json()
                .encode()
            )
            print("... message received")


async def test_post_task_log_message_dask(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    dask_task: DaskTask,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
    logs_rabbitmq_consumer: AsyncMock,
):
    log_message = faker.pystr()
    await post_tasks_log_message(
        initialized_app, tasks=[dask_task], message=log_message, level=0
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {LoggerRabbitMessage.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
            )
            logs_rabbitmq_consumer.assert_called_once_with(
                LoggerRabbitMessage(
                    node_id=node_id,
                    project_id=project_id,
                    user_id=user_id,
                    messages=[f"[cluster] {log_message}"],
                    log_level=0,
                )
                .model_dump_json()
                .encode()
            )
            print("... message received")


async def test_post_task_progress_message_docker(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    running_service_tasks: Callable[[dict[DockerLabelKey, str]], Awaitable[list[Task]]],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
    faker: Faker,
    progress_rabbitmq_consumer: AsyncMock,
):
    docker_tasks = await running_service_tasks(
        osparc_docker_label_keys.to_simcore_runtime_docker_labels(),
    )
    assert len(docker_tasks) == 1

    progress_value = faker.pyfloat(min_value=0)
    await post_tasks_progress_message(
        initialized_app,
        tasks=docker_tasks,
        progress=progress_value,
        progress_type=ProgressType.CLUSTER_UP_SCALING,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {ProgressRabbitMessageNode.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
            )
            progress_rabbitmq_consumer.assert_called_once_with(
                ProgressRabbitMessageNode(
                    node_id=osparc_docker_label_keys.node_id,
                    project_id=osparc_docker_label_keys.project_id,
                    user_id=osparc_docker_label_keys.user_id,
                    progress_type=ProgressType.CLUSTER_UP_SCALING,
                    report=ProgressReport(actual_value=progress_value, total=1),
                )
                .model_dump_json()
                .encode()
            )
            print("... message received")


async def test_post_task_progress_message_dask(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    dask_task: DaskTask,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
    progress_rabbitmq_consumer: AsyncMock,
):
    progress_value = faker.pyfloat(min_value=0)
    await post_tasks_progress_message(
        initialized_app,
        tasks=[dask_task],
        progress=progress_value,
        progress_type=ProgressType.CLUSTER_UP_SCALING,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {ProgressRabbitMessageNode.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
            )
            progress_rabbitmq_consumer.assert_called_once_with(
                ProgressRabbitMessageNode(
                    node_id=node_id,
                    project_id=project_id,
                    user_id=user_id,
                    progress_type=ProgressType.CLUSTER_UP_SCALING,
                    report=ProgressReport(actual_value=progress_value, total=1),
                )
                .model_dump_json()
                .encode()
            )
            print("... message received")


async def test_post_task_messages_does_not_raise_if_service_has_no_labels(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    running_service_tasks: Callable[[dict[DockerLabelKey, str]], Awaitable[list[Task]]],
    faker: Faker,
):
    docker_tasks = await running_service_tasks({})
    assert len(docker_tasks) == 1

    # this shall not raise any exception even if the task does not contain
    # the necessary labels
    await post_tasks_log_message(
        initialized_app, tasks=docker_tasks, message=faker.pystr(), level=0
    )
    await post_tasks_progress_message(
        initialized_app,
        tasks=docker_tasks,
        progress=faker.pyfloat(min_value=0),
        progress_type=ProgressType.CLUSTER_UP_SCALING,
    )


async def test_post_task_messages_does_not_raise_if_dask_task_key_is_invalid(
    disable_autoscaling_background_task,
    disable_buffers_pool_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    dask_task_with_invalid_key: DaskTask,
    faker: Faker,
):
    # this shall not raise any exception even if the task does not contain
    # the necessary labels
    await post_tasks_log_message(
        initialized_app,
        tasks=[dask_task_with_invalid_key],
        message=faker.pystr(),
        level=0,
    )
    await post_tasks_progress_message(
        initialized_app,
        tasks=[dask_task_with_invalid_key],
        progress=faker.pyfloat(min_value=0),
        progress_type=ProgressType.CLUSTER_UP_SCALING,
    )
