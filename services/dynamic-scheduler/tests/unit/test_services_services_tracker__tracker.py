# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Callable, Generator
from copy import deepcopy
from unittest.mock import AsyncMock, call

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.services_tracker._resource_manager import (
    TrackerCleanupContext,
)
from simcore_service_dynamic_scheduler.services.services_tracker.api import (
    ServicesTracker,
    get_services_tracker,
)

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, redis_service: RedisSettings
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def services_tracker(disable_rabbitmq_setup: None, app: FastAPI) -> ServicesTracker:
    return get_services_tracker(app)


@pytest.fixture
def service_status_event_sequence_factory(
    mocker: MockerFixture,
) -> Callable[[dict[NodeID, list[NodeGet | DynamicServiceGet | NodeGetIdle]]], None]:
    """After all the events in the event sequence are used it always returns None"""

    def _(
        service_status_sequence: dict[
            NodeID, list[NodeGet | DynamicServiceGet | NodeGetIdle]
        ]
    ) -> None:
        # NOTE: when all the items inside service_status_sequence are used it returns None
        def _gen_status(
            node_id: NodeID,
        ) -> Generator[NodeGet | DynamicServiceGet | NodeGetIdle | None, None, None]:
            yield from service_status_sequence.get(node_id, [])  # noqa: UP028

            # if no more entries found always yeld None
            while True:
                yield None

        generators: dict[
            NodeID,
            Generator[NodeGet | DynamicServiceGet | NodeGetIdle | None, None, None],
        ] = {}

        async def _mock_get(
            identifier: NodeID,
        ) -> NodeGet | DynamicServiceGet | NodeGetIdle | None:
            if identifier not in generators:
                generators[identifier] = _gen_status(identifier)

            return next(generators[identifier])

        base_module = "simcore_service_dynamic_scheduler.services.services_tracker._resource_manager"
        mocker.patch(
            f"{base_module}.ServicesManager.get",
            side_effect=_mock_get,
        )

    return _


@pytest.fixture
def get_node_id(faker: Faker) -> Callable[[], NodeID]:
    def _() -> NodeID:
        return faker.uuid4(cast_to=None)

    return _


async def test__fixture_service_status_event_sequence_factory(
    services_tracker: ServicesTracker,
    service_status_event_sequence_factory: Callable[
        [dict[NodeID, list[NodeGet | DynamicServiceGet | NodeGetIdle]]], None
    ],
    get_node_id: Callable[[], NodeID],
):
    async def _assert_always_returns_none(node_id: NodeID) -> None:
        for _ in range(10):
            assert await services_tracker.get(identifier=node_id) is None

    async def _assert_sequence_order(
        node_id: NodeID, sequence: list[NodeGet | DynamicServiceGet | NodeGetIdle]
    ) -> None:
        for expected_get_result in sequence:
            assert await services_tracker.get(identifier=node_id) == expected_get_result

    # CASE 1: no sequence provided
    missing_node_id = get_node_id()
    service_status_event_sequence_factory({})

    await _assert_always_returns_none(missing_node_id)

    # CASE 2: sequence is empty
    empty_sequence_node_id = get_node_id()
    service_status_event_sequence_factory({empty_sequence_node_id: []})

    await _assert_always_returns_none(empty_sequence_node_id)

    # CASE 3: sequence with 1 element
    node_id_idle_once = get_node_id()
    single_element_sequence: list[NodeGet | DynamicServiceGet | NodeGetIdle] = [
        NodeGetIdle(service_state="idle", service_uuid=node_id_idle_once)
    ]
    service_status_event_sequence_factory({node_id_idle_once: single_element_sequence})

    await _assert_sequence_order(node_id_idle_once, single_element_sequence)
    await _assert_always_returns_none(node_id_idle_once)

    # CASE 4: mix element sequence
    node_id_mix_sequence = get_node_id()
    mixed_sequence: list[NodeGet | DynamicServiceGet | NodeGetIdle] = [
        NodeGet.parse_obj(NodeGet.Config.schema_extra["example"]),
        NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
        DynamicServiceGet.parse_obj(
            DynamicServiceGet.Config.schema_extra["examples"][0]
        ),
        NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
        NodeGetIdle(service_state="idle", service_uuid=node_id_mix_sequence),
    ]
    service_status_event_sequence_factory({node_id_mix_sequence: mixed_sequence})

    await _assert_sequence_order(node_id_mix_sequence, mixed_sequence)
    await _assert_always_returns_none(node_id_mix_sequence)


@pytest.fixture
def mock_director_v2_api(
    mocker: MockerFixture,
    service_status_event_sequence_factory: Callable[
        [dict[NodeID, list[NodeGet | DynamicServiceGet | NodeGetIdle]]], None
    ],
) -> None:
    # mocks the following inside ServicesManager: `_create` and `_destroy`
    # to change what `get` returns use `service_status_event_sequence_factory` fixture
    base_module = (
        "simcore_service_dynamic_scheduler.services.services_tracker._resource_manager"
    )
    mocker.patch(f"{base_module}.director_v2_api.run_dynamic_service")
    mocker.patch(f"{base_module}.director_v2_api.stop_dynamic_service")
    # mocks the get to reply with nothing
    service_status_event_sequence_factory({})


@pytest.fixture
def mock_publish_message(mocker: MockerFixture) -> AsyncMock:
    base_module = "simcore_service_dynamic_scheduler.services.services_tracker._tracker"
    mock = AsyncMock()
    mocker.patch(f"{base_module}.publish_message", mock)
    return mock


async def _manual_check_services_status(services_tracker: ServicesTracker) -> None:
    await services_tracker._check_services_status_task()  # pylint:disable=protected-access # noqa: SLF001


async def _create_service(services_tracker: ServicesTracker, node_id: NodeID) -> None:
    # add a service to tracking
    rpc_dynamic_service_create = RPCDynamicServiceCreate.parse_obj(
        RPCDynamicServiceCreate.Config.schema_extra["example"]
    )
    rpc_dynamic_service_create.node_uuid = node_id
    await services_tracker.create(
        cleanup_context=TrackerCleanupContext(
            simcore_user_agent="", save_state=True, primary_group_id=1
        ),
        rpc_dynamic_service_create=rpc_dynamic_service_create,
    )


async def test_services_tracker_notification_publishing(
    mock_director_v2_api: None,
    mock_publish_message: AsyncMock,
    services_tracker: ServicesTracker,
    get_node_id: Callable[[], NodeID],
    service_status_event_sequence_factory: Callable[
        [dict[NodeID, list[NodeGet | DynamicServiceGet | NodeGetIdle]]], None
    ],
    app: FastAPI,
):
    # nothing happens for now
    await _manual_check_services_status(services_tracker)
    assert mock_publish_message.call_args_list == []

    # after a service is created, the mock returns no status change
    # checking this
    new_service_node_id = get_node_id()
    await _create_service(services_tracker, new_service_node_id)
    await _manual_check_services_status(services_tracker)
    assert mock_publish_message.call_args_list == []

    # after the status of the new service is mocked new_service this should be returned
    new_service_status_sequence: list[NodeGet | DynamicServiceGet | NodeGetIdle] = [
        NodeGet.parse_obj(NodeGet.Config.schema_extra["example"]),
    ]
    service_status_event_sequence_factory(
        {new_service_node_id: new_service_status_sequence}
    )

    await _manual_check_services_status(services_tracker)
    assert len(mock_publish_message.call_args_list) == 1
    mock_publish_message.assert_awaited_once_with(
        app, node_id=new_service_node_id, service_status=new_service_status_sequence[0]
    )
    mock_publish_message.reset_mock()


async def test_services_tracker_notification_sequence(
    mock_director_v2_api: None,
    mock_publish_message: AsyncMock,
    services_tracker: ServicesTracker,
    get_node_id: Callable[[], NodeID],
    service_status_event_sequence_factory: Callable[
        [dict[NodeID, list[NodeGet | DynamicServiceGet | NodeGetIdle]]], None
    ],
    app: FastAPI,
):
    assert len(mock_publish_message.call_args_list) == 0

    # create a new service
    node_id = get_node_id()
    await _create_service(services_tracker, node_id)
    await _manual_check_services_status(services_tracker)
    assert mock_publish_message.call_args_list == []

    # create a sequence of events where some of them repeat
    event_node_get = NodeGet.parse_obj(NodeGet.Config.schema_extra["example"])
    event_dynamic_service_get = DynamicServiceGet.parse_obj(
        DynamicServiceGet.Config.schema_extra["examples"][0]
    )
    event_node_get_idle = NodeGetIdle.parse_obj(
        NodeGetIdle.Config.schema_extra["example"]
    )

    service_status_sequence: list[NodeGet | DynamicServiceGet | NodeGetIdle] = [
        *[deepcopy(event_node_get) for _ in range(3)],
        *[deepcopy(event_dynamic_service_get) for _ in range(4)],
        *[deepcopy(event_node_get_idle) for _ in range(10)],
        *[deepcopy(event_dynamic_service_get) for _ in range(1)],
        *[deepcopy(event_node_get) for _ in range(1)],
    ]
    service_status_event_sequence_factory({node_id: service_status_sequence})

    # make sure all events are processed
    events_to_process = len(service_status_sequence) * 2
    for _ in range(events_to_process):
        await _manual_check_services_status(services_tracker)

    # identify service status changes
    services_status_changes: list[NodeGet | DynamicServiceGet | NodeGetIdle] = []

    last_service_status: NodeGet | DynamicServiceGet | NodeGetIdle | None = None
    for service_status in service_status_sequence:
        if service_status != last_service_status:
            last_service_status = service_status
            services_status_changes.append(service_status)

    # check events appear in expected sequence
    assert len(services_status_changes) == 5
    assert len(mock_publish_message.call_args_list) == 5

    for i, service_status_change in enumerate(services_status_changes):
        assert mock_publish_message.await_args_list[i] == call(
            app, node_id=node_id, service_status=service_status_change
        )
