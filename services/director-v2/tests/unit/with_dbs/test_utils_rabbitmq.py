# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-statements


import random
from typing import Any, Awaitable, Callable
from unittest import mock

import pytest
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import InstrumentationRabbitMessage
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.utils.rabbitmq import (
    publish_service_started_metrics,
    publish_service_stopped_metrics,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock(return_value=True)


async def _assert_message_received(
    mocked_message_parser: mock.AsyncMock,
    expected_call_count: int,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            # NOTE: this sleep is here to ensure that there are not multiple messages coming in
            print(
                f"--> waiting for rabbitmq message [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )
            assert mocked_message_parser.call_count == expected_call_count
            print(
                f"<-- rabbitmq message received after [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )


async def test_publish_service_started_metrics(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    registered_user: Callable[..., dict],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
    simcore_user_agent: str,
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    mocked_message_parser: mock.AsyncMock,
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")

    user = registered_user()
    prj = await project(user, workbench=fake_workbench_without_outputs)
    pipeline(
        project_id=prj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = tasks(user, prj)
    assert len(comp_tasks) > 0
    random_task = random.choice(comp_tasks)  # noqa: S311

    await consumer.subscribe(
        InstrumentationRabbitMessage.get_channel_name(), mocked_message_parser
    )
    await publish_service_started_metrics(
        publisher,
        user_id=user["id"],
        simcore_user_agent=simcore_user_agent,
        task=random_task,
    )
    await _assert_message_received(mocked_message_parser, 1)


async def test_publish_service_stopped_metrics(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    registered_user: Callable[..., dict],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
    simcore_user_agent: str,
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    mocked_message_parser: mock.AsyncMock,
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")

    user = registered_user()
    prj = await project(user, workbench=fake_workbench_without_outputs)
    pipeline(
        project_id=prj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = tasks(user, prj)
    assert len(comp_tasks) > 0
    random_task = random.choice(comp_tasks)  # noqa: S311

    await consumer.subscribe(
        InstrumentationRabbitMessage.get_channel_name(), mocked_message_parser
    )
    random_task_final_state = random.choice(list(RunningState))  # noqa: S311
    await publish_service_stopped_metrics(
        publisher,
        user_id=user["id"],
        simcore_user_agent=simcore_user_agent,
        task=random_task,
        task_final_state=random_task_final_state,
    )
    await _assert_message_received(mocked_message_parser, 1)
