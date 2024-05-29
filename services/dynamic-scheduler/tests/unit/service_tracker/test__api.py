# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from uuid import uuid4

import pytest
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    get_tracked,
    remove_tracked,
    set_tracked_as_running,
    set_tracked_as_stopped,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    UserRequestedState,
)

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


async def test_services_tracer_workflow(app: FastAPI):
    node_id: NodeID = uuid4()

    # service does not exist
    assert await get_tracked(app, node_id) is None

    # service requested as to be in RUNNING
    await set_tracked_as_running(app, node_id)
    tracked_model = await get_tracked(app, node_id)
    assert tracked_model
    assert tracked_model.requested_sate == UserRequestedState.RUNNING

    # service requested as to be in STOPPED
    await set_tracked_as_stopped(app, node_id)
    tracked_model = await get_tracked(app, node_id)
    assert tracked_model
    assert tracked_model.requested_sate == UserRequestedState.STOPPED

    # remove service
    await remove_tracked(app, node_id)
    assert await get_tracked(app, node_id) is None
