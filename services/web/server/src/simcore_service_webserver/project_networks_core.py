import logging
from collections import namedtuple
from typing import Any, Dict, Set

from aiohttp.web import Application
from models_library.projects import ProjectID
from models_library.project_networks import (
    DockerNetworkAlias,
    DockerNetworkName,
    NetworksWithAliases,
    ContainerAliases,
    validate_network_alias,
    validate_network_name,
    PROJECT_NETWORK_PREFIX,
)
from pydantic import ValidationError
from servicelib.utils import logged_gather

from . import director_v2_api
from .project_networks_db import get_project_networks, update_project_networks

logger = logging.getLogger(__name__)

_ToRemove = namedtuple("_ToRemove", "project_id, node_id, network_name")
_ToAdd = namedtuple("_ToAdd", "project_id, node_id, network_name, network_alias")


def _network_name(project_id: ProjectID, user_defined: str) -> DockerNetworkName:
    network_name = f"{PROJECT_NETWORK_PREFIX}_{project_id}_{user_defined}"
    return validate_network_name(network_name)


def _network_alias(label: str) -> DockerNetworkAlias:
    return validate_network_alias(label)


async def _send_network_configuration_to_dynamic_sidecar(
    app: Application,
    project_id: ProjectID,
    new_networks_with_aliases: NetworksWithAliases,
    existing_networks_with_aliases: NetworksWithAliases,
) -> None:
    """
    Propagates the network configuration to the dynamic-sidecars.
    Note:
    - All unused networks will be removed from each service.
    - All required networks will be attached to each service.
    - Networks which are in use will not be removed.
    """

    # REMOVING
    to_remove_items: Set[_ToRemove] = set()

    # if network no longer exist remove it from all nodes
    for new_network_name, node_ids_and_aliases in new_networks_with_aliases.items():
        if new_network_name not in existing_networks_with_aliases:
            for node_id in node_ids_and_aliases:
                to_remove_items.add(
                    _ToRemove(
                        project_id=project_id,
                        node_id=node_id,
                        network_name=new_network_name,
                    )
                )
    # if node does not exist for the network, remove it
    # if alias is different remove the network
    for new_network_name, node_ids_and_aliases in new_networks_with_aliases.items():
        existing_node_ids_and_aliases = existing_networks_with_aliases.get(
            new_network_name, {}
        )
        for node_id, alias in node_ids_and_aliases.items():
            # node does not exist
            if node_id not in existing_node_ids_and_aliases:
                to_remove_items.add(
                    _ToRemove(
                        project_id=project_id,
                        node_id=node_id,
                        network_name=new_network_name,
                    )
                )
            else:
                existing_alias = existing_networks_with_aliases[new_network_name][
                    node_id
                ]
                # alias is different
                if existing_alias != alias:
                    to_remove_items.add(
                        _ToRemove(
                            project_id=project_id,
                            node_id=node_id,
                            network_name=new_network_name,
                        )
                    )

    await logged_gather(
        *[
            director_v2_api.detach_network_from_dynamic_sidecar(
                app=app,
                project_id=to_remove.project_id,
                node_id=to_remove.node_id,
                network_name=to_remove.network_name,
            )
            for to_remove in to_remove_items
        ]
    )

    # ADDING
    to_add_items: Set[_ToAdd] = set()
    # all aliases which are different or missing should be added
    for new_network_name, node_ids_and_aliases in new_networks_with_aliases.items():
        existing_node_ids_and_aliases = existing_networks_with_aliases.get(
            new_network_name, {}
        )
        for node_id, alias in node_ids_and_aliases.items():
            existing_alias = existing_node_ids_and_aliases.get(node_id)
            if alias != existing_alias:
                to_add_items.add(
                    _ToAdd(
                        project_id=project_id,
                        node_id=node_id,
                        network_name=new_network_name,
                        network_alias=alias,
                    )
                )

    await logged_gather(
        *[
            director_v2_api.attach_network_to_dynamic_sidecar(
                app=app,
                project_id=to_add.project_id,
                node_id=to_add.node_id,
                network_name=to_add.network_name,
                network_alias=to_add.network_alias,
            )
            for to_add in to_add_items
        ]
    )


async def _get_networks_with_aliases_for_default_network(
    app: Application, project_id: ProjectID, new_workbench: Dict[str, Any]
) -> NetworksWithAliases:
    """
    Until a proper UI is in place all container need to
    be on the same network.
    Return an updated version of the project_networks
    """
    new_networks_with_aliases: NetworksWithAliases = NetworksWithAliases.parse_obj({})

    default_network = _network_name(project_id, "default")
    new_networks_with_aliases[default_network] = ContainerAliases.parse_obj({})

    for node_uuid, node_content in new_workbench.items():
        # only add dynamic-sidecar nodes
        if not await director_v2_api.requires_dynamic_sidecar(
            app,
            service_key=node_content["key"],
            service_version=node_content["version"],
        ):
            continue

        # only add if network label is valid, otherwise it will be skipped
        try:
            network_alias = _network_alias(node_content["label"])
        except ValidationError:
            # TODO: need to inform frontend somehow about this issue!!!
            # maybe a Log message will be fine, when renaming
            # maybe we need to refactor the message delivery in the dynamic-sidecar
            # and pull it in a shared module for this, for now
            logger.warning(
                "Service with label '%s' cannot be added to the network %s",
                node_content["label"],
                default_network,
            )
            continue

        new_networks_with_aliases[default_network][f"{node_uuid}"] = network_alias

    return new_networks_with_aliases


async def update_from_workbench(
    app: Application, project_id: ProjectID, workbench: Dict[str, Any]
) -> None:
    """
    Automatically updates the project networks based on the incoming new workbench.
    """

    existing_project_networks = await get_project_networks(
        app=app, project_id=project_id
    )
    existing_networks_with_aliases = existing_project_networks.networks_with_aliases

    # NOTE: when UI is in place this is no longer required
    # for now all services are placed on the same default network
    new_networks_with_aliases = await _get_networks_with_aliases_for_default_network(
        app=app, project_id=project_id, new_workbench=workbench
    )
    logger.debug("%s", f"{existing_networks_with_aliases=}")
    await update_project_networks(
        app=app, project_id=project_id, networks_with_aliases=new_networks_with_aliases
    )

    await _send_network_configuration_to_dynamic_sidecar(
        app=app,
        project_id=project_id,
        new_networks_with_aliases=new_networks_with_aliases,
        existing_networks_with_aliases=existing_networks_with_aliases,
    )
