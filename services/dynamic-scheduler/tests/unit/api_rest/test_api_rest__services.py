# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from collections.abc import Iterator

import pytest
import respx
from faker import Faker
from fastapi import status
from httpx import AsyncClient
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler._meta import API_VTAG


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None, app_environment: EnvVarsDict
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def service_state() -> DynamicServiceGet:
    return DynamicServiceGet.parse_obj(
        DynamicServiceGet.Config.schema_extra["examples"][1]
    )


@pytest.fixture
def mock_director_v2(
    node_id: NodeID, service_state: DynamicServiceGet
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v1",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get(f"/dynamic-services/{node_id}").respond(
            status.HTTP_200_OK, text=service_state.json()
        )
        yield None


async def test_get_status(mock_director_v2: None, client: AsyncClient, node_id: NodeID):
    response = await client.get(f"/{API_VTAG}/services/{node_id}")
    assert response.status_code == status.HTTP_200_OK
    assert DynamicServiceGet.parse_raw(response.text)
