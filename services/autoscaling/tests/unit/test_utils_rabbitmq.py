# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments


from collections.abc import Awaitable, Callable
from typing import Any

import aiodocker
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerLabelKey, StandardSimcoreDockerLabels
from models_library.generated_models.docker_rest_api import Service, Task
from models_library.progress_bar import ProgressReport
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressType,
)
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.utils.rabbitmq import (
    post_task_log_message,
    post_task_progress_message,
)
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


# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


async def test_post_task_log_message(
    disable_dynamic_service_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocker: MockerFixture,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
    faker: Faker,
):
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    client = create_rabbitmq_client("pytest_consumer")
    await client.subscribe(
        LoggerRabbitMessage.get_channel_name(),
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS],
    )

    service_with_labels = await create_service(
        task_template,
        osparc_docker_label_keys.to_simcore_runtime_docker_labels(),
        "running",
    )
    assert service_with_labels.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_labels.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    log_message = faker.pystr()
    await post_task_log_message(initialized_app, service_tasks[0], log_message, 0)

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {LoggerRabbitMessage.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
            )
            mocked_message_handler.assert_called_once_with(
                LoggerRabbitMessage(
                    node_id=osparc_docker_label_keys.node_id,
                    project_id=osparc_docker_label_keys.project_id,
                    user_id=osparc_docker_label_keys.user_id,
                    messages=[f"[cluster] {log_message}"],
                    log_level=0,
                )
                .json()
                .encode()
            )
            print("... message received")


async def test_post_task_log_message_does_not_raise_if_service_has_no_labels(
    disable_dynamic_service_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    faker: Faker,
):
    service_without_labels = await create_service(task_template, {}, "running")
    assert service_without_labels.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_without_labels.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    # this shall not raise any exception even if the task does not contain
    # the necessary labels
    await post_task_log_message(initialized_app, service_tasks[0], faker.pystr(), 0)


async def test_post_task_progress_message(
    disable_dynamic_service_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocker: MockerFixture,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
    faker: Faker,
):
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    client = create_rabbitmq_client("pytest_consumer")
    await client.subscribe(
        ProgressRabbitMessageNode.get_channel_name(),
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS],
    )

    service_with_labels = await create_service(
        task_template,
        osparc_docker_label_keys.to_simcore_runtime_docker_labels(),
        "running",
    )
    assert service_with_labels.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_labels.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    progress_value = faker.pyfloat(min_value=0)
    await post_task_progress_message(initialized_app, service_tasks[0], progress_value)

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {ProgressRabbitMessageNode.get_channel_name()}, {attempt.retry_state.retry_object.statistics}"
            )
            mocked_message_handler.assert_called_once_with(
                ProgressRabbitMessageNode(
                    node_id=osparc_docker_label_keys.node_id,
                    project_id=osparc_docker_label_keys.project_id,
                    user_id=osparc_docker_label_keys.user_id,
                    progress_type=ProgressType.CLUSTER_UP_SCALING,
                    report=ProgressReport(actual_value=progress_value, total=1),
                )
                .json()
                .encode()
            )
            print("... message received")


async def test_post_task_progress_does_not_raise_if_service_has_no_labels(
    disable_dynamic_service_background_task,
    enabled_rabbitmq: RabbitSettings,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    faker: Faker,
):
    service_without_labels = await create_service(task_template, {}, "running")
    assert service_without_labels.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_without_labels.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    # this shall not raise any exception even if the task does not contain
    # the necessary labels
    await post_task_progress_message(
        initialized_app, service_tasks[0], faker.pyfloat(min_value=0)
    )
