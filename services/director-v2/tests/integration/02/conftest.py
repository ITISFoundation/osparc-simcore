# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator
from uuid import uuid4

import aiodocker
from pydantic import TypeAdapter
import pytest
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
)
from models_library.projects_networks import ProjectsNetworks
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pytest_mock.plugin import MockerFixture


@pytest.fixture(scope="session")
def network_name() -> str:
    return "pytest-simcore_interactive_services_subnet"


@pytest.fixture
async def ensure_swarm_and_networks(
    network_name: str, docker_swarm: None
) -> AsyncIterator[None]:
    """
    Make sure to always have a docker swarm network.
    If one is not present crete one. There can not be more then one.
    """

    async with aiodocker.Docker() as docker_client:
        # if network dose not exist create and remove it
        create_and_remove_network = True
        for network_data in await docker_client.networks.list():
            if network_data["Name"] == network_name:
                create_and_remove_network = False
                break
        docker_network = None
        if create_and_remove_network:
            network_config = {
                "Name": network_name,
                "Driver": "overlay",
                "Attachable": True,
                "Internal": False,
                "Scope": "swarm",
            }
            docker_network = await docker_client.networks.create(network_config)

        yield

        if create_and_remove_network and docker_network:
            network = await docker_client.networks.get(docker_network.id)
            assert await network.delete() is True


@pytest.fixture
def mock_projects_networks_repository(mocker: MockerFixture) -> None:
    mocker.patch(
        (
            "simcore_service_director_v2.modules.db.repositories."
            "projects_networks.ProjectsNetworksRepository.get_projects_networks"
        ),
        return_value=ProjectsNetworks.model_validate(
            {"project_uuid": uuid4(), "networks_with_aliases": {}}
        ),
    )


@pytest.fixture
def service_resources() -> ServiceResourcesDict:
    return TypeAdapter(ServiceResourcesDict).validate_python(
        ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"][0],
    )


@pytest.fixture
def mock_resource_usage_tracker(mocker: MockerFixture) -> None:
    base_module = "simcore_service_director_v2.modules.resource_usage_tracker_client"
    service_pricing_plan = PricingPlanGet.model_validate(
        PricingPlanGet.model_config["json_schema_extra"]["examples"][1]
    )
    for unit in service_pricing_plan.pricing_units:
        unit.specific_info.aws_ec2_instances.clear()
    mocker.patch(
        f"{base_module}.ResourceUsageTrackerClient.get_default_service_pricing_plan",
        return_value=service_pricing_plan,
    )
