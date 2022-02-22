import logging
import json
from collections import namedtuple
from typing import Any, Dict, Set
from uuid import UUID

from aiohttp.web import Application
from models_library.projects import ProjectID
from models_library.sharing_networks import (
    DockerNetworkAlias,
    DockerNetworkName,
    SharingNetworks,
    ContainerAliases,
    validate_network_alias,
    validate_network_name,
)
from pydantic import ValidationError
from servicelib.utils import logged_gather

from . import director_v2_api

logger = logging.getLogger(__name__)

SHARING_NETWORK_PREFIX = "shr-ntwrk"

_ToRemove = namedtuple("_ToRemove", "project_id, node_id, network_name")
_ToAdd = namedtuple("_ToAdd", "project_id, node_id, network_name, network_alias")


def _network_name(project_id: ProjectID, user_defined: str) -> DockerNetworkName:
    network_name = f"{SHARING_NETWORK_PREFIX}_{project_id}_{user_defined}"
    return validate_network_name(network_name)


def _network_alias(label: str) -> DockerNetworkAlias:
    return validate_network_alias(label)


async def _send_network_configuration_to_dynamic_sidecar(
    app: Application,
    project_id: ProjectID,
    new_sharing_networks: SharingNetworks,  # TODO: rename to new
    sharing_networks: SharingNetworks,  # TODO. rename to existing
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
    for new_network_name, node_ids_and_aliases in new_sharing_networks.items():
        if new_network_name not in sharing_networks:
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
    for new_network_name, node_ids_and_aliases in new_sharing_networks.items():
        existing_node_ids_and_aliases = sharing_networks.get(new_network_name, {})
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
                existing_alias = existing_node_ids_and_aliases[node_id]
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
    for new_network_name, node_ids_and_aliases in new_sharing_networks.items():
        existing_node_ids_and_aliases = sharing_networks.get(new_network_name, {})
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


async def _get_sharing_networks_for_default_network(
    app: Application, new_project_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Until a proper UI is in place all container need to
    be on the same network.
    Return an updated version of the sharing_networks
    """
    new_sharing_networks: SharingNetworks = SharingNetworks.parse_obj({})

    default_network = _network_name(UUID(new_project_data["uuid"]), "default")
    new_sharing_networks[default_network] = ContainerAliases.parse_obj({})

    for node_uuid, node_content in new_project_data["workbench"].items():
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
            # mauybe we need to refactor the message delivery in the dynamic-sidecar
            # and pull it in a shared module for this, for now
            logger.warning(
                "Service with label '%s' cannot be added to the network %s",
                node_content["label"],
                default_network,
            )
            continue

        new_sharing_networks[default_network][UUID(node_uuid)] = network_alias

    return new_sharing_networks.dict(by_alias=True)


async def propagate_changes(
    app: Application, current_project: Dict[str, Any], new_project_data: Dict[str, Any]
) -> None:
    """
    Automatically updates the networks based on the incoming new sharing_networks.
    It is assumed that this will be updated by the fronted.
    NOTE: this needs to be called before saving the `new_project_data` to the database
    """

    old_sharing_networks = SharingNetworks.parse_obj(current_project["sharingNetworks"])

    # NOTE: when UI is in place this is no longer required
    # for now all services are placed on the same default network
    new_project_data[
        "sharingNetworks"
    ] = await _get_sharing_networks_for_default_network(app, new_project_data)

    logger.debug("new_sharing_networks=%s", new_project_data["sharingNetworks"])

    await _send_network_configuration_to_dynamic_sidecar(
        app=app,
        project_id=UUID(new_project_data["uuid"]),
        new_sharing_networks=SharingNetworks.parse_obj(
            new_project_data["sharingNetworks"]
        ),
        sharing_networks=old_sharing_networks,
    )
