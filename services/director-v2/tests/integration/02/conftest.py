# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from uuid import uuid4

import aiodocker
import pytest
from models_library.projects_networks import ProjectsNetworks
from pytest_mock.plugin import MockerFixture


@pytest.fixture(scope="session")
def network_name() -> str:
    return "pytest-simcore_interactive_services_subnet"


@pytest.fixture
async def ensure_swarm_and_networks(network_name: str, docker_swarm: None):
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
        return_value=ProjectsNetworks.parse_obj(
            dict(project_uuid=uuid4(), networks_with_aliases={})
        ),
    )
