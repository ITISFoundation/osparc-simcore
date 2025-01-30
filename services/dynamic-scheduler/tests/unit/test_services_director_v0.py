# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from collections.abc import Iterator

import pytest
import respx
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.director_v0 import (
    DirectorV0PublicClient,
)


@pytest.fixture
def app_environment(
    disable_redis_setup: None,
    disable_rabbitmq_setup: None,
    disable_service_tracker_setup: None,
    disable_deferred_manager_setup: None,
    disable_notifier_setup: None,
    disable_status_monitor_setup: None,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def legacy_service_details(
    node_id: NodeID, project_id: ProjectID
) -> RunningDynamicServiceDetails:
    return TypeAdapter(RunningDynamicServiceDetails).validate_python(
        RunningDynamicServiceDetails.model_json_schema()["examples"][0]
    )


@pytest.fixture
def mock_director_v0(
    node_id: NodeID, legacy_service_details: RunningDynamicServiceDetails
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director:8000",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        respx_mock.request(
            method="GET", path=f"/v0/running_interactive_services/{node_id}"
        ).respond(
            status_code=200,
            json={
                "data": legacy_service_details.model_dump(mode="json"),
                "error": None,
            },
        )

        respx_mock.request(
            method="GET", path="/v0/running_interactive_services"
        ).respond(
            status_code=200,
            json={"data": [legacy_service_details.model_dump(mode="json")]},
        )

        yield


async def test_get_running_service_details(
    mock_director_v0: None,
    app: FastAPI,
    node_id: NodeID,
    legacy_service_details: RunningDynamicServiceDetails,
):
    client = DirectorV0PublicClient.get_from_app_state(app)
    result = await client.get_running_service_details(node_id)
    assert result == legacy_service_details


async def test_get_running_services(
    mock_director_v0: None,
    app: FastAPI,
    legacy_service_details: RunningDynamicServiceDetails,
):
    client = DirectorV0PublicClient.get_from_app_state(app)
    result = await client.get_running_services()
    assert result == [legacy_service_details]
