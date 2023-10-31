# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from settings_library.redis import RedisSettings
from simcore_service_director_v2.modules.service_status_observer._store import (
    StatusesStore,
    get_statuses_store,
)

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    # "redis-commander",
]


@pytest.fixture
def mock_env(
    disable_postgres: None,
    disable_rabbitmq: None,
    redis_service: RedisSettings,
    docker_swarm: None,
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "S3_ENDPOINT": "endpoint",
            "S3_ACCESS_KEY": "access_key",
            "S3_SECRET_KEY": "secret_key",
            "S3_BUCKET_NAME": "bucket_name",
            "S3_SECURE": "false",
        },
    )


@pytest.fixture
async def statuses_store(initialized_app: FastAPI) -> StatusesStore:
    return get_statuses_store(initialized_app)


@pytest.mark.parametrize("service_count", [1, 100])
async def test_statuses_tore_workflow(
    statuses_store: StatusesStore, faker: Faker, service_count: int
):
    node_ids: set[NodeID] = {faker.uuid4(cast_to=None) for _ in range(service_count)}

    status = RunningDynamicServiceDetails.parse_obj(
        RunningDynamicServiceDetails.Config.schema_extra["examples"][0]
    )

    # insert
    for node_id in node_ids:
        await statuses_store.set_status(node_id, status)

    # read
    for node_id in node_ids:
        read_status = await statuses_store.get_status(node_id)
        assert read_status == status

    assert await statuses_store.get_node_ids() == node_ids

    # remove
    for node_id in node_ids:
        await statuses_store.remove_status(node_id)

    assert await statuses_store.get_node_ids() == set()


async def test_statuses_store_expired_are_no_longer_present(
    mocker: MockerFixture, statuses_store: StatusesStore, faker: Faker
):
    MOCK_CACHE_TTL: float = 1
    mocker.patch(
        "simcore_service_director_v2.modules.service_status_observer._store.CACHE_ENTRIES_TTL_S",
        MOCK_CACHE_TTL,
    )

    node_id: NodeID = faker.uuid4(cast_to=None)

    status = RunningDynamicServiceDetails.parse_obj(
        RunningDynamicServiceDetails.Config.schema_extra["examples"][0]
    )

    assert await statuses_store.get_status(node_id) is None

    await statuses_store.set_status(node_id, status)

    # checks that key is present
    assert await statuses_store.get_status(node_id) == status
    assert await statuses_store.get_node_ids() == {node_id}

    await asyncio.sleep(MOCK_CACHE_TTL)

    # node_id is no longer present and was removed from cache
    assert await statuses_store.get_status(node_id) is None
    assert await statuses_store.get_node_ids() == set()
