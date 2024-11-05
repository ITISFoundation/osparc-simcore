import logging
import urllib.parse
from typing import NamedTuple
from uuid import UUID

from models_library.projects import NodesDict, ProjectAtDB, ProjectID
from models_library.projects_networks import (
    PROJECT_NETWORK_PREFIX,
    ContainerAliases,
    DockerNetworkAlias,
    DockerNetworkName,
    NetworksWithAliases,
    ProjectsNetworks,
)
from models_library.projects_nodes_io import NodeIDStr
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from pydantic import TypeAdapter, ValidationError
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather

from ..core.errors import ProjectNetworkNotFoundError
from ..modules.db.repositories.projects import ProjectsRepository
from ..modules.db.repositories.projects_networks import ProjectsNetworksRepository
from ..modules.director_v0 import DirectorV0Client
from ..modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler

logger = logging.getLogger(__name__)


class _ToRemove(NamedTuple):
    project_id: ProjectID
    node_id: NodeIDStr
    network_name: str


class _ToAdd(NamedTuple):
    project_id: ProjectID
    node_id: NodeIDStr
    network_name: str
    network_alias: DockerNetworkAlias


def _network_name(project_id: ProjectID, user_defined: str) -> DockerNetworkName:
    network_name = f"{PROJECT_NETWORK_PREFIX}_{project_id}_{user_defined}"
    return TypeAdapter(DockerNetworkName).validate_python(network_name)


async def requires_dynamic_sidecar(
    service_key: str,
    service_version: str,
    director_v0_client: DirectorV0Client,
) -> bool:
    decoded_service_key = urllib.parse.unquote_plus(service_key)

    # check the type of service, if not dynamic do
    # not fetch the labels
    # (simcore)/(services)/(comp|dynamic|frontend)
    service_type = decoded_service_key.split("/")[2]
    if service_type != "dynamic":
        return False

    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion.model_validate(
                {"key": decoded_service_key, "version": service_version}
            )
        )
    )
    requires_dynamic_sidecar_: bool = simcore_service_labels.needs_dynamic_sidecar
    return requires_dynamic_sidecar_


async def _send_network_configuration_to_dynamic_sidecar(
    scheduler: DynamicSidecarsScheduler,
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
    to_remove_items: set[_ToRemove] = set()

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
            new_network_name, {}  # type: ignore[arg-type] # -> should refactor code to not use DictModel it is useless
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
            scheduler.detach_project_network(
                node_id=UUID(to_remove.node_id),
                project_network=to_remove.network_name,
            )
            for to_remove in to_remove_items
        ]
    )

    # ADDING
    to_add_items: set[_ToAdd] = set()
    # all aliases which are different or missing should be added
    for new_network_name, node_ids_and_aliases in new_networks_with_aliases.items():
        existing_node_ids_and_aliases = existing_networks_with_aliases.get(
            new_network_name, {}  # type: ignore[arg-type] # -> should refactor code to not use DictModel it is useless
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
            scheduler.attach_project_network(
                node_id=UUID(to_add.node_id),
                project_network=to_add.network_name,
                network_alias=to_add.network_alias,
            )
            for to_add in to_add_items
        ]
    )


async def _get_networks_with_aliases_for_default_network(
    project_id: ProjectID,
    user_id: UserID,
    new_workbench: NodesDict,
    director_v0_client: DirectorV0Client,
    rabbitmq_client: RabbitMQClient,
) -> NetworksWithAliases:
    """
    Until a proper UI is in place all container need to
    be on the same network.
    Return an updated version of the projects_networks
    """
    new_networks_with_aliases: NetworksWithAliases = NetworksWithAliases.model_validate({})

    default_network = _network_name(project_id, "default")
    new_networks_with_aliases[default_network] = ContainerAliases.model_validate({})

    for node_uuid, node_content in new_workbench.items():
        # only add dynamic-sidecar nodes
        if not await requires_dynamic_sidecar(
            service_key=node_content.key,
            service_version=node_content.version,
            director_v0_client=director_v0_client,
        ):
            continue

        # only add if network label is valid, otherwise it will be skipped
        try:
            network_alias = TypeAdapter(DockerNetworkAlias).validate_python(node_content.label)
        except ValidationError:
            message = LoggerRabbitMessage(
                user_id=user_id,
                project_id=project_id,
                node_id=UUID(node_uuid),
                messages=[
                    # pylint:disable=anomalous-backslash-in-string
                    (
                        f"Service with label '{node_content.label}' cannot be "
                        "identified on service network due to invalid name. "
                        "To communicate over the network, please rename the "
                        "service alphanumeric characters <64 characters, "
                        r"e.g. re.sub(r'\W+', '', SERVICE_NAME). "
                        f"Network name is {default_network}"
                    )
                ],
                log_level=logging.WARNING,
            )
            await rabbitmq_client.publish(message.channel_name, message)
            continue

        new_networks_with_aliases[default_network][
            NodeIDStr(f"{node_uuid}")
        ] = network_alias

    return new_networks_with_aliases


async def update_from_workbench(
    projects_networks_repository: ProjectsNetworksRepository,
    projects_repository: ProjectsRepository,
    scheduler: DynamicSidecarsScheduler,
    director_v0_client: DirectorV0Client,
    rabbitmq_client: RabbitMQClient,
    project_id: ProjectID,
) -> None:
    """
    Automatically updates the project networks based on the incoming new workbench.
    """

    try:
        existing_projects_networks = (
            await projects_networks_repository.get_projects_networks(
                project_id=project_id
            )
        )
    except ProjectNetworkNotFoundError:
        existing_projects_networks = ProjectsNetworks.model_validate(
            {"project_uuid": project_id, "networks_with_aliases": {}}
        )

    existing_networks_with_aliases = existing_projects_networks.networks_with_aliases

    # NOTE: when UI is in place this is no longer required
    # for now all services are placed on the same default network
    project: ProjectAtDB = await projects_repository.get_project(project_id)
    assert project.prj_owner  # nosec
    new_networks_with_aliases = await _get_networks_with_aliases_for_default_network(
        project_id=project_id,
        user_id=project.prj_owner,
        new_workbench=project.workbench,
        director_v0_client=director_v0_client,
        rabbitmq_client=rabbitmq_client,
    )
    logger.debug("%s", f"{existing_networks_with_aliases=}")
    await projects_networks_repository.upsert_projects_networks(
        project_id=project_id, networks_with_aliases=new_networks_with_aliases
    )

    await _send_network_configuration_to_dynamic_sidecar(
        scheduler=scheduler,
        project_id=project_id,
        new_networks_with_aliases=new_networks_with_aliases,
        existing_networks_with_aliases=existing_networks_with_aliases,
    )
