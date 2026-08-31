# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo
from models_library.services_resources import (
    ResourcesDict,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    InsufficientInstanceResourcesError,
)
from simcore_service_webserver.projects._projects_service import (
    update_project_node_resources_from_hardware_info,
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
def scaled_node_resources() -> ServiceResourcesDict:
    resources = TypeAdapter(ResourcesDict).validate_python(
        {
            "CPU": {"limit": 5.6, "reservation": 5.6},
            "RAM": {"limit": "13GiB", "reservation": "13GiB"},
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
def mock_rpc_calls(mocker: MockerFixture, node_resources: ServiceResourcesDict) -> None:
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


async def _call(mocked_app: AsyncMock, hardware_info: HardwareInfo) -> None:
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


async def test_persists_the_resources_computed_by_director_v2(
    mock_rpc_calls: None,
    mock_project_db_api: AsyncMock,
    mocked_app: AsyncMock,
    hardware_info: HardwareInfo,
    scaled_node_resources: ServiceResourcesDict,
    mocker: MockerFixture,
):
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.scale_service_resources_for_instance_type",
        AsyncMock(return_value=scaled_node_resources),
    )

    await _call(mocked_app, hardware_info)

    mock_project_db_api.update_project_node.assert_called_once()
    assert mock_project_db_api.update_project_node.call_args.kwargs[
        "required_resources"
    ] == ServiceResourcesDictHelpers.create_jsonable(scaled_node_resources)


async def test_raises_when_director_v2_reports_machine_too_small(
    mock_rpc_calls: None,
    mock_project_db_api: AsyncMock,
    mocked_app: AsyncMock,
    hardware_info: HardwareInfo,
    mocker: MockerFixture,
):
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.scale_service_resources_for_instance_type",
        AsyncMock(side_effect=InsufficientInstanceResourcesError),
    )

    with pytest.raises(InsufficientInstanceResourcesError):
        await _call(mocked_app, hardware_info)

    mock_project_db_api.update_project_node.assert_not_called()
    # the project must NOT be updated when there are insufficient resources
    mock_project_db_api.update_project_node.assert_not_called()
