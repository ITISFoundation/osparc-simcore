# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ResourcesDict,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from servicelib.docker_utils import estimate_dynamic_sidecar_resources_from_ec2_instance
from simcore_service_webserver.projects._projects_service import (
    update_project_node_resources_from_hardware_info,
)
from simcore_service_webserver.projects.exceptions import (
    InsufficientResourcesForHelperContainersError,
)

_EC2_INSTANCE_TYPE = EC2InstanceTypeGet(
    name="c6a.4xlarge",
    cpus=8,
    ram=TypeAdapter(ByteSize).validate_python("16GiB"),
)


@pytest.fixture
def mocked_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def hardware_info() -> HardwareInfo:
    return HardwareInfo(aws_ec2_instances=[_EC2_INSTANCE_TYPE.name])


@pytest.fixture
def node_resources() -> ServiceResourcesDict:
    resources = TypeAdapter(ResourcesDict).validate_python(
        {
            "CPU": {"limit": 0.1, "reservation": 0.1},
            "RAM": {"limit": "128MiB", "reservation": "128MiB"},
        }
    )
    return ServiceResourcesDictHelpers.create_from_single_service(
        image="simcore/services/dynamic/some-service:1.0.0",
        resources=resources,
    )


@pytest.fixture
def mock_project_db_api(mocker: MockerFixture) -> AsyncMock:
    mocked_db = AsyncMock()
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.ProjectDBAPI.get_from_app_context",
        return_value=mocked_db,
    )
    return mocked_db


@pytest.fixture
def mock_rpc_calls(
    mocker: MockerFixture,
    node_resources: ServiceResourcesDict,
    helper_containers_overhead: tuple[float, ByteSize],
) -> None:
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.get_rabbitmq_rpc_client",
        return_value=AsyncMock(),
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.get_instance_type_details",
        AsyncMock(return_value=[_EC2_INSTANCE_TYPE]),
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.get_project_node_resources",
        AsyncMock(return_value=node_resources),
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.get_helper_containers_resources",
        AsyncMock(return_value=helper_containers_overhead),
    )


@pytest.mark.parametrize(
    "helper_containers_overhead",
    [
        pytest.param((7.5, TypeAdapter(ByteSize).validate_python("1MiB")), id="cpu_overhead_too_large"),
        pytest.param((0.1, TypeAdapter(ByteSize).validate_python("13GiB")), id="ram_overhead_too_large"),
        pytest.param((7.5, TypeAdapter(ByteSize).validate_python("13GiB")), id="both_overheads_too_large"),
    ],
)
async def test_raises_when_helper_containers_leave_insufficient_resources(
    mock_rpc_calls: None,
    mock_project_db_api: AsyncMock,
    mocked_app: AsyncMock,
    hardware_info: HardwareInfo,
    helper_containers_overhead: tuple[float, ByteSize],
):
    sidecar_cpus, sidecar_ram = estimate_dynamic_sidecar_resources_from_ec2_instance(
        _EC2_INSTANCE_TYPE.cpus, _EC2_INSTANCE_TYPE.ram
    )
    cpu_overhead, ram_overhead = helper_containers_overhead
    expected_cpus = sidecar_cpus - cpu_overhead
    expected_ram = int(sidecar_ram - ram_overhead)

    with pytest.raises(InsufficientResourcesForHelperContainersError) as exc_info:
        await update_project_node_resources_from_hardware_info(
            mocked_app,
            user_id=UserID(1),
            project_id=ProjectID("00000000-0000-0000-0000-000000000001"),
            node_id=NodeID("00000000-0000-0000-0000-000000000002"),
            service_key="simcore/services/dynamic/some-service",
            service_version="1.0.0",
            product_name="osparc",
            hardware_info=hardware_info,
        )

    assert exc_info.value.cpus == expected_cpus
    assert exc_info.value.ram == expected_ram
    # the project must NOT be updated when there are insufficient resources
    mock_project_db_api.update_project_node.assert_not_called()


@pytest.mark.parametrize(
    "helper_containers_overhead",
    [(0.5, TypeAdapter(ByteSize).validate_python("512MiB"))],
    ids=["small_overhead"],
)
async def test_update_project_node_resources_from_hardware_info_succeeds_when_resources_are_sufficient(
    mock_rpc_calls: None,
    mock_project_db_api: AsyncMock,
    mocked_app: AsyncMock,
    hardware_info: HardwareInfo,
    helper_containers_overhead: tuple[float, ByteSize],
):
    sidecar_cpus, sidecar_ram = estimate_dynamic_sidecar_resources_from_ec2_instance(
        _EC2_INSTANCE_TYPE.cpus, _EC2_INSTANCE_TYPE.ram
    )
    cpu_overhead, ram_overhead = helper_containers_overhead
    expected_cpus = sidecar_cpus - cpu_overhead
    expected_ram = int(sidecar_ram - ram_overhead)

    await update_project_node_resources_from_hardware_info(
        mocked_app,
        user_id=UserID(1),
        project_id=ProjectID("00000000-0000-0000-0000-000000000001"),
        node_id=NodeID("00000000-0000-0000-0000-000000000002"),
        service_key="simcore/services/dynamic/some-service",
        service_version="1.0.0",
        product_name="osparc",
        hardware_info=hardware_info,
    )

    mock_project_db_api.update_project_node.assert_awaited_once()
    _, kwargs = mock_project_db_api.update_project_node.call_args
    updated_resources = kwargs["required_resources"]
    scaled = updated_resources[DEFAULT_SINGLE_SERVICE_NAME]["resources"]
    assert scaled["CPU"]["limit"] == expected_cpus
    assert scaled["RAM"]["limit"] == expected_ram
