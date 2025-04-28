import pytest
from dask_task_models_library.container_tasks.utils import (
    generate_dask_job_id,
    parse_dask_job_id,
)
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter


@pytest.fixture(
    params=["simcore/service/comp/some/fake/service/key", "dockerhub-style/service_key"]
)
def service_key(request) -> ServiceKey:
    return request.param


@pytest.fixture()
def service_version() -> str:
    return "1234.32432.2344"


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return TypeAdapter(UserID).validate_python(faker.pyint(min_value=1))


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


def test_dask_job_id_serialization(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    dask_job_id = generate_dask_job_id(
        service_key, service_version, user_id, project_id, node_id
    )
    (
        parsed_service_key,
        parsed_service_version,
        parsed_user_id,
        parsed_project_id,
        parsed_node_id,
    ) = parse_dask_job_id(dask_job_id)
    assert service_key == parsed_service_key
    assert service_version == parsed_service_version
    assert user_id == parsed_user_id
    assert project_id == parsed_project_id
    assert node_id == parsed_node_id
