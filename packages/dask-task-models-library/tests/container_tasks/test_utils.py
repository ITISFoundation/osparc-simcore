# pylint: disable=too-many-positional-arguments
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import pytest
from dask_task_models_library.container_tasks.utils import (
    generate_dask_job_id,
    parse_dask_job_id,
)
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID, UserIDAdapter


@pytest.fixture(params=["simcore/service/comp/some/fake/service/key", "dockerhub-style/service_key"])
def service_key(request) -> ServiceKey:
    return request.param


@pytest.fixture()
def service_version() -> str:
    return "1234.32432.2344"


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserIDAdapter.validate_python(faker.pyint(min_value=1))


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.fixture
def run_id(faker: Faker) -> int:
    return faker.pyint(min_value=1)


def test_dask_job_id_serialization(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    run_id: int,
):
    dask_job_id = generate_dask_job_id(service_key, service_version, user_id, project_id, node_id, run_id=run_id)
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


def test_dask_job_id_with_run_id_is_deterministic(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
):
    run_id = faker.pyint(min_value=1)
    dask_job_id = generate_dask_job_id(service_key, service_version, user_id, project_id, node_id, run_id=run_id)
    # same (node, run) resubmission reuses the exact same dask key
    assert dask_job_id == generate_dask_job_id(
        service_key, service_version, user_id, project_id, node_id, run_id=run_id
    )
    # a different run must get a different dask key
    assert dask_job_id != generate_dask_job_id(
        service_key, service_version, user_id, project_id, node_id, run_id=run_id + 1
    )
    # still parses the same way regardless of the run_id suffix
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


def test_parse_dask_job_id_is_compatible_with_old_uuid_style_job_id(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    faker: Faker,
):
    """job ids generated before run_id existed used a random uuid as the last segment
    instead of runid_<int>; parse_dask_job_id must keep parsing those (jobs already
    in flight when this change is deployed)."""
    old_style_job_id = (
        f"{service_key}:{service_version}:userid_{user_id}:projectid_{project_id}:nodeid_{node_id}:uuid_{faker.uuid4()}"
    )
    (
        parsed_service_key,
        parsed_service_version,
        parsed_user_id,
        parsed_project_id,
        parsed_node_id,
    ) = parse_dask_job_id(old_style_job_id)
    assert service_key == parsed_service_key
    assert service_version == parsed_service_version
    assert user_id == parsed_user_id
    assert project_id == parsed_project_id
    assert node_id == parsed_node_id
