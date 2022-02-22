import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

import yaml
from fastapi.applications import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import ComposeSpecLabel, PathMappingsLabel
from models_library.sharing_networks import SharingNetworks
from settings_library.docker_registry import RegistrySettings

from ...modules.dynamic_sidecar.docker_api import get_or_create_networks_ids
from ._constants import CONTAINER_NAME
from .docker_service_specs import MATCH_SERVICE_VERSION, MATCH_SIMCORE_REGISTRY

EnvKeyEqValueList = List[str]
EnvVarsMap = Dict[str, Optional[str]]

logger = logging.getLogger(__name__)


class _environment_section:
    """the 'environment' field in a docker-compose can be either a dict (EnvVarsMap)
    or a list of "key=value" (EnvKeyEqValueList)

    These helpers can resolve parsing and exporting between these formats

    SEE https://docs.docker.com/compose/compose-file/compose-file-v3/#environment
    """

    @staticmethod
    def parse(environment: Union[EnvVarsMap, EnvKeyEqValueList]) -> EnvVarsMap:
        envs = {}
        if isinstance(environment, list):
            for key_eq_value in environment:
                assert isinstance(key_eq_value, str)  # nosec
                key, value, *_ = key_eq_value.split("=", maxsplit=1) + [
                    None,
                ]  # type: ignore
                envs[key] = value
        else:
            assert isinstance(environment, dict)  # nosec
            envs = deepcopy(environment)
        return envs

    @staticmethod
    def export_as_list(environment: EnvVarsMap) -> EnvKeyEqValueList:
        envs = []
        for key, value in environment.items():
            if value is None:
                envs.append(f"{key}")
            else:
                envs.append(f"{key}={value}")
        return envs


def _inject_paths_mappings(
    service_spec: Dict[str, Any], path_mappings: PathMappingsLabel
) -> None:
    for service_name in service_spec["services"]:
        service_content = service_spec["services"][service_name]

        env_vars: EnvVarsMap = _environment_section.parse(
            service_content.get("environment", {})
        )
        env_vars["DY_SIDECAR_PATH_INPUTS"] = f"{path_mappings.inputs_path}"
        env_vars["DY_SIDECAR_PATH_OUTPUTS"] = f"{path_mappings.outputs_path}"
        env_vars[
            "DY_SIDECAR_STATE_PATHS"
        ] = f"{json.dumps([f'{p}' for p in path_mappings.state_paths])}"

        service_content["environment"] = _environment_section.export_as_list(env_vars)


def _replace_env_vars_in_compose_spec(
    stringified_service_spec: str, resolved_registry_url: str, service_tag: str
) -> str:
    stringified_service_spec = stringified_service_spec.replace(
        MATCH_SIMCORE_REGISTRY, resolved_registry_url
    )
    stringified_service_spec = stringified_service_spec.replace(
        MATCH_SERVICE_VERSION, service_tag
    )
    return stringified_service_spec


def _inject_proxy_network_configuration(
    service_spec: Dict[str, Any],
    target_container: str,
    dynamic_sidecar_network_name: str,
) -> None:
    """
    Injects network configuration to allow the service
    to be accessible on `uuid.services.SERVICE_DNS`
    """

    # add external network to existing networks defined in the container
    networks = service_spec.get("networks", {})
    networks[dynamic_sidecar_network_name] = {
        "external": {"name": dynamic_sidecar_network_name},
        "driver": "overlay",
    }
    service_spec["networks"] = networks

    # attach overlay network to container
    target_container_spec = service_spec["services"][target_container]
    container_networks = target_container_spec.get("networks", [])
    container_networks.append(dynamic_sidecar_network_name)
    target_container_spec["networks"] = container_networks


async def _inject_sharing_networks_configuration(
    service_spec: Dict[str, Any],
    sharing_networks: SharingNetworks,
    node_uuid: NodeID,
    target_container: str,
    project_id: ProjectID,
) -> None:
    logger.debug("Extracting networks from %s", f"{sharing_networks=}")
    networks = service_spec.get("networks", {})

    for network_name, node_aliases in sharing_networks.items():
        logger.debug("DEBUG: %s", f"{network_name=}")
        if node_uuid not in node_aliases:
            # this node is not part of this sharing network skipping
            continue

        # attach network to service spec
        networks[network_name] = {
            "external": {"name": network_name},
            "driver": "overlay",
        }

        # make sure network exits, if not create it
        await get_or_create_networks_ids([network_name], project_id)

        # attach network to container spec
        alias = node_aliases[node_uuid]
        logger.debug("DEBUG: %s", f"{alias=}")
        # ensure the containers always have the same names
        for k, container_name in enumerate(sorted(service_spec["services"].keys())):
            logger.debug("DEBUG: %s", f"{container_name=}")
            container_spec = service_spec["services"][container_name]
            container_networks = container_spec.get("networks", {})

            # object might be a list need to convert to a dict
            if isinstance(container_networks, list):
                container_networks = {x: {} for x in container_networks}

            # by defaults all containers are marked as `{alias}-0`, `{alias}-1`, etc...
            # the target container also inherits the non enumerated alias
            # this allows for more advanced usages in the context of multi container
            # applications
            container_aliases = [f"{alias}-{k}"]
            if container_name == target_container:
                # by definition the entrypoint container will be exposed as the `alias`
                container_aliases.append(alias)
            container_networks[network_name] = {"aliases": container_aliases}

            container_spec["networks"] = container_networks

    # make sure networks is updates if missing
    service_spec["networks"] = networks


async def assemble_spec(
    app: FastAPI,
    service_key: str,
    service_tag: str,
    paths_mapping: PathMappingsLabel,
    compose_spec: Optional[ComposeSpecLabel],
    container_http_entry: Optional[str],
    dynamic_sidecar_network_name: str,
    sharing_networks: SharingNetworks,
    node_uuid: NodeID,
    project_id: ProjectID,
) -> str:
    """
    returns a docker-compose spec used by
    the dynamic-sidecar to start the service
    """

    docker_registry_settings: RegistrySettings = (
        app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY
    )

    docker_compose_version = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_DOCKER_COMPOSE_VERSION
    )

    # when no compose yaml file was provided
    if compose_spec is None:
        service_spec: Dict[str, Any] = {
            "version": docker_compose_version,
            "services": {
                CONTAINER_NAME: {
                    "image": f"{docker_registry_settings.resolved_registry_url}/{service_key}:{service_tag}"
                }
            },
        }
        container_name = CONTAINER_NAME
    else:
        service_spec = compose_spec
        container_name = container_http_entry

    assert service_spec is not None  # nosec
    assert container_name is not None  # nosec

    _inject_proxy_network_configuration(
        service_spec=service_spec,
        target_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
    )

    await _inject_sharing_networks_configuration(
        service_spec=service_spec,
        sharing_networks=sharing_networks,
        node_uuid=node_uuid,
        target_container=container_name,
        project_id=project_id,
    )

    _inject_paths_mappings(service_spec, paths_mapping)

    stringified_service_spec = yaml.safe_dump(service_spec)
    stringified_service_spec = _replace_env_vars_in_compose_spec(
        stringified_service_spec=stringified_service_spec,
        resolved_registry_url=docker_registry_settings.resolved_registry_url,
        service_tag=service_tag,
    )

    return stringified_service_spec
