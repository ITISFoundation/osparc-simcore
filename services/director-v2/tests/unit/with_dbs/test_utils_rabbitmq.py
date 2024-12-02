# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-statements


import datetime
import random
from collections.abc import Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
from faker import Faker
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeIDStr
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    RabbitResourceTrackingBaseMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.services import ServiceKey, ServiceType, ServiceVersion
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.utils.rabbitmq import (
    publish_service_resource_tracking_heartbeat,
    publish_service_resource_tracking_started,
    publish_service_resource_tracking_stopped,
    publish_service_started_metrics,
    publish_service_stopped_metrics,
)
from tenacity.asyncio import AsyncRetrying
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
    message_parser: Callable,
) -> list:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> waiting for rabbitmq message [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )
            assert mocked_message_parser.call_count == expected_call_count
            print(
                f"<-- rabbitmq message received after [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )
    return [
        message_parser(mocked_message_parser.call_args_list[c].args[0])
        for c in range(expected_call_count)
    ]


@pytest.fixture
def user(registered_user: Callable[..., dict]) -> dict:
    return registered_user()


@pytest.fixture
async def project(
    user: dict[str, Any],
    fake_workbench_without_outputs: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
) -> ProjectAtDB:
    return await project(user, workbench=fake_workbench_without_outputs)


@pytest.fixture
async def tasks(
    user: dict[str, Any],
    project: ProjectAtDB,
    fake_workbench_adjacency: dict[str, Any],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks: Callable[..., Awaitable[list[CompTaskAtDB]]],
) -> list[CompTaskAtDB]:
    await create_pipeline(
        project_id=f"{project.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks(user, project)
    assert len(comp_tasks) > 0
    return comp_tasks


async def test_publish_service_started_metrics(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    user: dict[str, Any],
    simcore_user_agent: str,
    tasks: list[CompTaskAtDB],
    mocked_message_parser: mock.AsyncMock,
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")

    await consumer.subscribe(
        InstrumentationRabbitMessage.get_channel_name(), mocked_message_parser
    )
    await publish_service_started_metrics(
        publisher,
        user_id=user["id"],
        simcore_user_agent=simcore_user_agent,
        task=random.choice(tasks),  # noqa: S311
    )
    await _assert_message_received(
        mocked_message_parser, 1, InstrumentationRabbitMessage.model_validate_json
    )


async def test_publish_service_stopped_metrics(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    user: dict[str, Any],
    simcore_user_agent: str,
    tasks: list[CompTaskAtDB],
    mocked_message_parser: mock.AsyncMock,
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")

    await consumer.subscribe(
        InstrumentationRabbitMessage.get_channel_name(), mocked_message_parser
    )
    await publish_service_stopped_metrics(
        publisher,
        user_id=user["id"],
        simcore_user_agent=simcore_user_agent,
        task=random.choice(tasks),  # noqa: S311
        task_final_state=random.choice(list(RunningState)),  # noqa: S311
    )
    await _assert_message_received(
        mocked_message_parser, 1, InstrumentationRabbitMessage.model_validate_json
    )


async def test_publish_service_resource_tracking_started(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    user: dict[str, Any],
    project: ProjectAtDB,
    simcore_user_agent: str,
    tasks: list[CompTaskAtDB],
    mocked_message_parser: mock.AsyncMock,
    faker: Faker,
    osparc_product_name: str,
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")

    random_task = random.choice(tasks)  # noqa: S311

    await consumer.subscribe(
        RabbitResourceTrackingBaseMessage.get_channel_name(), mocked_message_parser
    )
    random_service_run_id = faker.pystr()
    before_publication_time = datetime.datetime.now(datetime.UTC)
    await publish_service_resource_tracking_started(
        publisher,
        service_run_id=random_service_run_id,
        wallet_id=faker.pyint(min_value=1),
        wallet_name=faker.pystr(),
        pricing_plan_id=None,
        pricing_unit_id=None,
        pricing_unit_cost_id=None,
        product_name=osparc_product_name,
        simcore_user_agent=simcore_user_agent,
        user_id=user["id"],
        user_email=faker.email(),
        project_id=project.uuid,
        project_name=project.name,
        node_id=random_task.node_id,
        node_name=project.workbench[NodeIDStr(f"{random_task.node_id}")].label,
        parent_project_id=None,
        parent_node_id=None,
        root_parent_project_id=None,
        root_parent_project_name=None,
        root_parent_node_id=None,
        service_key=ServiceKey(random_task.image.name),
        service_version=ServiceVersion(random_task.image.tag),
        service_type=ServiceType.COMPUTATIONAL,
        service_resources={},
        service_additional_metadata=faker.pydict(),
    )
    after_publication_time = datetime.datetime.now(datetime.UTC)
    received_messages = await _assert_message_received(
        mocked_message_parser,
        1,
        RabbitResourceTrackingStartedMessage.model_validate_json,
    )
    assert isinstance(received_messages[0], RabbitResourceTrackingStartedMessage)
    assert received_messages[0].service_run_id == random_service_run_id
    assert received_messages[0].created_at
    assert (
        before_publication_time
        < received_messages[0].created_at
        < after_publication_time
    )


async def test_publish_service_resource_tracking_stopped(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocked_message_parser: mock.AsyncMock,
    faker: Faker,
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")

    await consumer.subscribe(
        RabbitResourceTrackingBaseMessage.get_channel_name(), mocked_message_parser
    )
    random_service_run_id = faker.pystr()
    before_publication_time = datetime.datetime.now(datetime.UTC)
    await publish_service_resource_tracking_stopped(
        publisher,
        service_run_id=random_service_run_id,
        simcore_platform_status=random.choice(  # noqa: S311
            list(SimcorePlatformStatus)
        ),
    )
    after_publication_time = datetime.datetime.now(datetime.UTC)
    received_messages = await _assert_message_received(
        mocked_message_parser,
        1,
        RabbitResourceTrackingStoppedMessage.model_validate_json,
    )
    assert isinstance(received_messages[0], RabbitResourceTrackingStoppedMessage)
    assert received_messages[0].service_run_id == random_service_run_id
    assert received_messages[0].created_at
    assert (
        before_publication_time
        < received_messages[0].created_at
        < after_publication_time
    )


async def test_publish_service_resource_tracking_heartbeat(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocked_message_parser: mock.AsyncMock,
    faker: Faker,
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")

    await consumer.subscribe(
        RabbitResourceTrackingBaseMessage.get_channel_name(), mocked_message_parser
    )
    random_service_run_id = faker.pystr()
    before_publication_time = datetime.datetime.now(datetime.UTC)
    await publish_service_resource_tracking_heartbeat(
        publisher,
        service_run_id=random_service_run_id,
    )
    after_publication_time = datetime.datetime.now(datetime.UTC)
    received_messages = await _assert_message_received(
        mocked_message_parser,
        1,
        RabbitResourceTrackingHeartbeatMessage.model_validate_json,
    )
    assert isinstance(received_messages[0], RabbitResourceTrackingHeartbeatMessage)
    assert received_messages[0].service_run_id == random_service_run_id
    assert received_messages[0].created_at
    assert (
        before_publication_time
        < received_messages[0].created_at
        < after_publication_time
    )
