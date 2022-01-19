from typing import AsyncIterator, Dict
from _pytest.fixtures import fail_fixturefunc
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.sharing_networks import (
    SharingNetworks,
    DockerNetworkAlias,
    DockerNetworkName,
)

from contextlib import asynccontextmanager


_SHARING_NETWORKS: Dict[ProjectID, SharingNetworks] = {}


@asynccontextmanager
async def networks_manager(project_id: ProjectID) -> AsyncIterator[SharingNetworks]:
    # TODO replace implementation with loading and storing to the DB
    if project_id not in _SHARING_NETWORKS:
        _SHARING_NETWORKS[project_id] = {}

    yield _SHARING_NETWORKS[project_id]

    # add saving to the database once the object context manger finishes


class BaseNetworksException(Exception):
    pass


class InvalidServiceLabelException(BaseNetworksException):
    pass


class NetworkNotDefinedException(BaseNetworksException):
    pass


async def add_network(project_id: ProjectID, network_name: DockerNetworkName) -> None:
    """creates network if missing"""
    async with networks_manager(project_id) as project_networks:
        if network_name not in project_networks:
            project_networks[network_name] = {}


async def remove_network(
    project_id: ProjectID, network_name: DockerNetworkName
) -> None:
    """removes network if present"""
    async with networks_manager(project_id) as project_networks:
        if network_name in project_networks:
            # TODO: send an update before removing all to DV2 to remove delete network
            # and detach containers
            del project_networks[network_name]


async def add_node(
    project_id: ProjectID,
    node_id: NodeID,
    network_name: DockerNetworkName,
    network_alias: DockerNetworkAlias,
) -> None:
    """adds node to network or update network name"""

    send_update = False
    async with networks_manager(project_id) as project_networks:
        if network_name not in project_networks:
            raise NetworkNotDefinedException(f"Network {network_name} was not defined!")

        project_networks[network_name][node_id] = network_alias
        send_update = True

    if send_update:
        # TODO: send update to DV2
        pass


async def remove_node(
    project_id: ProjectID, network_name: DockerNetworkName, node_id: NodeID
) -> None:
    """removes node from network"""
    send_update = False
    async with networks_manager(project_id) as project_networks:
        if network_name not in project_networks:
            raise NetworkNotDefinedException(f"Network {network_name} was not defined!")

        if node_id in project_networks[network_name]:
            del project_networks[network_name][node_id]
            send_update = True

    if send_update:
        # TODO: send update to DV2
        pass


async def get_sharing_networks(project_id: ProjectID) -> Dict[str, Dict[str, str]]:
    def _transform_value(value: Dict[NodeID, str]) -> Dict[str, str]:
        return {str(k): v for k, v in value.items()}

    async with networks_manager(project_id) as project_networks:
        return {k: _transform_value(v) for k, v in project_networks.items()}
