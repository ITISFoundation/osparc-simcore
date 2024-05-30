# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from uuid import uuid4

import pytest
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.utils import logged_gather
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    TrackedServiceModel,
    UserRequestedState,
)
from simcore_service_dynamic_scheduler.services.service_tracker._setup import (
    get_tracker,
)
from simcore_service_dynamic_scheduler.services.service_tracker._tracker import (
    Tracker,
    _get_key,
)

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    disable_deferred_manager_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def tracker(app: FastAPI) -> Tracker:
    return get_tracker(app)


async def test_tracker_workflow(tracker: Tracker):
    node_id: NodeID = uuid4()

    # ensure does not already exist
    result = await tracker.load(node_id)
    assert result is None

    # node creation
    model = TrackedServiceModel(requested_sate=UserRequestedState.RUNNING)
    await tracker.save(node_id, model)

    # check if exists
    result = await tracker.load(node_id)
    assert result == model

    # remove and check is missing
    await tracker.delete(node_id)
    result = await tracker.load(node_id)
    assert result is None


@pytest.mark.parametrize("item_count", [100])
async def test_tracker_listing(tracker: Tracker, item_count: NonNegativeInt) -> None:
    assert await tracker.all() == {}

    model_to_insert = TrackedServiceModel(requested_sate=UserRequestedState.RUNNING)

    data_to_insert = {uuid4(): model_to_insert for _ in range(item_count)}

    await logged_gather(
        *[tracker.save(k, v) for k, v in data_to_insert.items()], max_concurrency=100
    )

    assert await tracker.all() == {_get_key(k): v for k, v in data_to_insert.items()}


async def test_remove_missing_key_does_not_raise_error(tracker: Tracker):
    await tracker.delete(uuid4())
