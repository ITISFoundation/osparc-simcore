# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from collections.abc import Iterator

import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_webserver.projects_nodes import NodeGet
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.director_v0 import (
    DirectorV0PublicClient,
)


@pytest.fixture
def app_environment(
    disable_generic_scheduler_lifespan: None,
    disable_postgres_lifespan: None,
    disable_redis_lifespan: None,
    disable_rabbitmq_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    disable_p_scheduler_lifespan: None,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def legacy_service_details() -> NodeGet:
    return TypeAdapter(NodeGet).validate_python(NodeGet.model_json_schema()["examples"][1])


@pytest.fixture
def missing_node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_director_v0(node_id: NodeID, legacy_service_details: NodeGet, missing_node_id: NodeID) -> Iterator[None]:
    with respx.mock(
        base_url="http://director:8000",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        respx_mock.request(method="GET", path=f"/v0/running_interactive_services/{node_id}").respond(
            status_code=status.HTTP_200_OK, json={"data": legacy_service_details.model_dump(mode="json"), "error": None}
        )
        respx_mock.request(method="GET", path=f"/v0/running_interactive_services/{missing_node_id}").respond(
            status_code=status.HTTP_404_NOT_FOUND,
            json={"error": {"errors": [f"Service with uuid {missing_node_id} was not found"]}},
        )

        respx_mock.request(method="GET", path="/v0/running_interactive_services").respond(
            status_code=status.HTTP_200_OK, json={"data": [legacy_service_details.model_dump(mode="json")]}
        )

        yield


async def test_get_running_service_details(
    mock_director_v0: None,
    app: FastAPI,
    node_id: NodeID,
    legacy_service_details: NodeGet,
    missing_node_id: NodeID,
):
    # 1. service that is present
    client = DirectorV0PublicClient.get_from_app_state(app)
    result = await client.get_running_service_details(node_id)
    assert result == legacy_service_details

    # 2. missing sevrvice
    assert await client.get_running_service_details(missing_node_id) is None


async def test_get_running_services(
    mock_director_v0: None,
    app: FastAPI,
    legacy_service_details: NodeGet,
):
    client = DirectorV0PublicClient.get_from_app_state(app)
    result = await client.get_running_services()
    assert result == [legacy_service_details]
