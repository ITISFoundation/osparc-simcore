from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from simcore_service_resource_usage_tracker.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)
from simcore_service_resource_usage_tracker.resource_tracker_process_messages import (
    _process_heartbeat_event,
    _process_start_event,
    _process_stop_event,
)

from .conftest import assert_service_runs_db_row

pytest_simcore_core_services_selection = [
    "postgres",
    # "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


# @pytest.fixture
# def rabbit_client_name(faker: Faker) -> str:
#     return faker.pystr()


# @pytest.fixture
# def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
#     return mocker.AsyncMock(return_value=True)


# @pytest.fixture
# def random_rabbit_message_heartbeat(
#     faker: Faker,
# ) -> Callable[..., RabbitResourceTrackingHeartbeatMessage]:
#     def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingHeartbeatMessage:
#         msg_config = {"service_run_id": faker.uuid4(), **kwargs}

#         return RabbitResourceTrackingHeartbeatMessage(**msg_config)

#     return _creator


# @pytest.fixture
# def random_rabbit_message_start(
#     faker: Faker,
# ) -> Callable[..., RabbitResourceTrackingStartedMessage]:
#     def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingStartedMessage:
#         msg_config = {
#             "channel_name": "io.simcore.service.tracking",
#             "service_run_id": faker.uuid4(),
#             "created_at": datetime.now(timezone.utc),
#             "wallet_id": faker.pyint(),
#             "wallet_name": faker.pystr(),
#             "product_name": "osparc",
#             "simcore_user_agent": faker.pystr(),
#             "user_id": faker.pyint(),
#             "user_email": faker.email(),
#             "project_id": faker.uuid4(),
#             "project_name": faker.pystr(),
#             "node_id": faker.uuid4(),
#             "node_name": faker.pystr(),
#             "service_key": "simcore/services/comp/itis/sleeper",
#             "service_version": "2.1.6",
#             "service_type": "computational",
#             "service_resources": {
#                 "container": {
#                     "image": "simcore/services/comp/itis/sleeper:2.1.6",
#                     "resources": {
#                         "CPU": {"limit": 0.1, "reservation": 0.1},
#                         "RAM": {"limit": 134217728, "reservation": 134217728},
#                     },
#                     "boot_modes": ["CPU"],
#                 }
#             },
#             "service_additional_metadata": {},
#             **kwargs,
#         }

#         return RabbitResourceTrackingStartedMessage(**msg_config)

#     return _creator


@pytest.mark.testit
async def test_process_event_functions(
    mocked_setup_rabbitmq,
    random_rabbit_message_start,
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_service_run_db,
    initialized_app,
):
    engine = initialized_app.state.engine

    msg = random_rabbit_message_start()
    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )
    await _process_start_event(resource_tacker_repo, msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[19] is None  # stopped_at
    assert output[20] == "RUNNING"  # status
    first_occurence_of_last_heartbeat_at = output[22]  # last_heartbeat_at

    heartbeat_msg = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=msg.service_run_id, created_at=datetime.now(tz=timezone.utc)
    )
    await _process_heartbeat_event(resource_tacker_repo, heartbeat_msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[19] is None  # stopped_at
    assert output[20] == "RUNNING"  # status
    first_occurence_of_last_heartbeat_at < output[22]  # last_heartbeat_at

    stopped_msg = RabbitResourceTrackingStoppedMessage(
        service_run_id=msg.service_run_id,
        created_at=datetime.now(tz=timezone.utc),
        simcore_platform_status=SimcorePlatformStatus.OK,
    )
    await _process_stop_event(resource_tacker_repo, stopped_msg)
    output = await assert_service_runs_db_row(postgres_db, msg.service_run_id)
    assert output[19] is not None  # stopped_at
    assert output[20] == "SUCCESS"  # status
