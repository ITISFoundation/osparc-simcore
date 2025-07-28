import pytest
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.services_types import ServiceKey, ServiceRunID, ServiceVersion
from models_library.users import UserID
from pydantic import PositiveInt, TypeAdapter
from pytest_simcore.helpers.faker_factories import (
    random_service_key,
    random_service_version,
)


@pytest.mark.parametrize(
    "user_id, project_id, node_id, iteration, expected_result",
    [
        (
            2,
            ProjectID("e08356e4-eb74-49e9-b769-2c26e34c61d9"),
            NodeID("a08356e4-eb74-49e9-b769-2c26e34c61d1"),
            5,
            "comp_2_e08356e4-eb74-49e9-b769-2c26e34c61d9_a08356e4-eb74-49e9-b769-2c26e34c61d1_5",
        )
    ],
)
def test_run_id_get_resource_tracking_run_id(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    iteration: PositiveInt,
    expected_result: str,
):
    resource_tracking_service_run_id = (
        ServiceRunID.get_resource_tracking_run_id_for_computational(
            user_id, project_id, node_id, iteration
        )
    )
    assert isinstance(resource_tracking_service_run_id, ServiceRunID)
    assert resource_tracking_service_run_id == expected_result


def test_get_resource_tracking_run_id_for_dynamic():
    assert isinstance(
        ServiceRunID.get_resource_tracking_run_id_for_dynamic(), ServiceRunID
    )


def test_faker_factories_random_service_key_and_version_are_in_sync():

    for _ in range(10):
        key = random_service_key()
        version = random_service_version()
        TypeAdapter(ServiceKey).validate_python(key)
        TypeAdapter(ServiceVersion).validate_python(version)
