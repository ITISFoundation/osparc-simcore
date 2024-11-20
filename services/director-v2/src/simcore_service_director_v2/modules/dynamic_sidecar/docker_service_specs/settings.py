import json
import logging
from collections import deque
from typing import Any, cast

from models_library.basic_types import EnvVarKey, PortInt
from models_library.boot_options import BootOption
from models_library.docker import (
    DockerPlacementConstraint,
    to_simcore_runtime_docker_label_key,
)
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
)
from models_library.services import ServiceKeyVersion
from models_library.services_resources import (
    CPU_100_PERCENT,
    DEFAULT_SINGLE_SERVICE_NAME,
    GIGA,
    MEMORY_1GB,
    ServiceResourcesDict,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.utils.docker_compose import (
    MATCH_IMAGE_END,
    MATCH_IMAGE_START,
    MATCH_SERVICE_VERSION,
)

from ....modules.director_v0 import DirectorV0Client
from ..errors import DynamicSidecarError

BOOT_OPTION_PREFIX = "DY_BOOT_OPTION"


log = logging.getLogger(__name__)


def _parse_mount_settings(settings: list[dict]) -> list[dict]:
    mounts = []
    for s in settings:
        log.debug("Retrieved mount settings %s", s)
        mount = {}
        mount["ReadOnly"] = True
        if "ReadOnly" in s and s["ReadOnly"] in ["false", "False", False]:
            mount["ReadOnly"] = False

        for field in ["Source", "Target", "Type"]:
            if field in s:
                mount[field] = s[field]
            else:
                log.warning(
                    "Mount settings have wrong format. Required keys [Source, Target, Type]"
                )
                continue

        log.debug("Append mount settings %s", mount)
        mounts.append(mount)

    return mounts


def _parse_env_settings(settings: list[str]) -> dict:
    envs = {}
    for s in settings:
        log.debug("Retrieved env settings %s", s)
        if "=" in s:
            parts = s.split("=")
            if len(parts) == 2:
                # will be forwarded to dynamic-sidecar spawned containers
                envs[f"FORWARD_ENV_{parts[0]}"] = parts[1]

        log.debug("Parsed env settings %s", s)

    return envs


def extract_service_port_from_settings(
    labels_service_settings: SimcoreServiceSettingsLabel,
) -> PortInt:
    param: SimcoreServiceSettingLabelEntry
    for param in labels_service_settings:
        # publishing port on the ingress network.
        if param.name == "ports" and param.setting_type == "int":  # backward comp
            return PortInt(param.value)
        # REST-API compatible
        if (
            param.setting_type == "EndpointSpec"
            and "Ports" in param.value
            and (
                isinstance(param.value["Ports"], list)
                and "TargetPort" in param.value["Ports"][0]
            )
        ):
            return PortInt(param.value["Ports"][0]["TargetPort"])
    msg = "service port not found!"
    raise ValueError(msg)


# pylint: disable=too-many-branches
def update_service_params_from_settings(
    labels_service_settings: SimcoreServiceSettingsLabel,
    create_service_params: dict[str, Any],
) -> None:
    param: SimcoreServiceSettingLabelEntry
    for param in labels_service_settings:
        # NOTE: the below capitalize addresses a bug in a lot of already in use services
        # where Resources was written in lower case
        if param.setting_type.capitalize() == "Resources":
            # python-API compatible for backward compatibility
            if "mem_limit" in param.value:
                create_service_params["task_template"]["Resources"]["Limits"][
                    "MemoryBytes"
                ] = param.value["mem_limit"]
            if "cpu_limit" in param.value:
                create_service_params["task_template"]["Resources"]["Limits"][
                    "NanoCPUs"
                ] = param.value["cpu_limit"]
            if "mem_reservation" in param.value:
                create_service_params["task_template"]["Resources"]["Reservations"][
                    "MemoryBytes"
                ] = param.value["mem_reservation"]
            if "cpu_reservation" in param.value:
                create_service_params["task_template"]["Resources"]["Reservations"][
                    "NanoCPUs"
                ] = param.value["cpu_reservation"]
            # REST-API compatible
            if "Limits" in param.value or "Reservations" in param.value:
                # NOTE: The Docker REST API reads Reservation when actually it's Reservations
                create_service_params["task_template"]["Resources"].update(param.value)

        # placement constraints
        elif (
            param.name == "constraints" or param.setting_type == "Constraints"
        ):  # python-API compatible
            create_service_params["task_template"]["Placement"][
                "Constraints"
            ] += param.value

        elif param.name == "env":
            log.debug("Found env parameter %s", param.value)
            env_settings = _parse_env_settings(param.value)
            if env_settings:
                create_service_params["task_template"]["ContainerSpec"]["Env"].update(
                    env_settings
                )
        elif param.name == "mount":
            log.debug("Found mount parameter %s", param.value)
            mount_settings: list[dict] = _parse_mount_settings(param.value)
            if mount_settings:
                create_service_params["task_template"]["ContainerSpec"][
                    "Mounts"
                ].extend(mount_settings)

    container_spec = create_service_params["task_template"]["ContainerSpec"]
    # set labels for CPU and Memory limits, for both service and container labels
    # NOTE: cpu-limit is a float not NanoCPUs!!
    container_spec["Labels"][
        f"{to_simcore_runtime_docker_label_key('cpu-limit')}"
    ] = str(
        float(create_service_params["task_template"]["Resources"]["Limits"]["NanoCPUs"])
        / (1 * 10**9)
    )
    create_service_params["labels"][
        f"{to_simcore_runtime_docker_label_key('cpu-limit')}"
    ] = str(
        float(create_service_params["task_template"]["Resources"]["Limits"]["NanoCPUs"])
        / (1 * 10**9)
    )
    container_spec["Labels"][
        f"{to_simcore_runtime_docker_label_key('memory-limit')}"
    ] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )
    create_service_params["labels"][
        f"{to_simcore_runtime_docker_label_key('memory-limit')}"
    ] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )

    # Cleanup repeated constraints.
    # Observed in deploy how constraint 'node.platform.os == linux' was appended many many times
    constraints = create_service_params["task_template"]["Placement"]["Constraints"]
    if constraints:
        assert isinstance(constraints, list)  # nosec
        constraints = list(set(constraints))


def _assemble_key(service_key: str, service_tag: str) -> str:
    return f"{service_key}:{service_tag}"


async def _extract_osparc_involved_service_labels(
    director_v0_client: DirectorV0Client,
    service_key: str,
    service_tag: str,
    service_labels: SimcoreServiceLabels,
) -> dict[str, SimcoreServiceLabels]:
    """
    Returns all the involved oSPARC services from the provided service labels.

    If the service contains a compose-spec that will also be parsed for images.
    Searches for images like the following in the spec:
    - `${SIMCORE_REGISTRY}/**SOME_SERVICE_NAME**:${SERVICE_VERSION}`
    - `${SIMCORE_REGISTRY}/**SOME_SERVICE_NAME**:1.2.3` where `1.2.3` is a hardcoded tag
    """

    # initialize with existing labels
    # stores labels mapped by image_name service:tag
    _default_key = _assemble_key(service_key=service_key, service_tag=service_tag)
    docker_image_name_by_services: dict[str, SimcoreServiceLabels] = {
        _default_key: service_labels
    }
    # maps form image_name to compose_spec key
    reverse_mapping: dict[str, str] = {_default_key: DEFAULT_SINGLE_SERVICE_NAME}

    def remap_to_compose_spec_key() -> dict[str, SimcoreServiceLabels]:
        # remaps from image_name as key to compose_spec key
        return {reverse_mapping[k]: v for k, v in docker_image_name_by_services.items()}

    compose_spec = service_labels.compose_spec
    if compose_spec is None:
        return remap_to_compose_spec_key()

    compose_spec_services = compose_spec.get("services", {})
    image = None
    for compose_service_key, service_data in compose_spec_services.items():
        image = service_data.get("image", None)
        if image is None:
            continue

        # if image dose not have this format skip:
        # - `${SIMCORE_REGISTRY}/**SOME_SERVICE_NAME**:${SERVICE_VERSION}`
        # - `${SIMCORE_REGISTRY}/**SOME_SERVICE_NAME**:1.2.3` a hardcoded tag
        if not image.startswith(MATCH_IMAGE_START) or ":" not in image:
            continue
        if not image.startswith(MATCH_IMAGE_START) or not image.endswith(
            MATCH_IMAGE_END
        ):
            continue

        # strips `${SIMCORE_REGISTRY}/`; replaces `${SERVICE_VERSION}` with `service_tag`
        osparc_image_key = image.replace(MATCH_SERVICE_VERSION, service_tag).replace(
            MATCH_IMAGE_START, ""
        )
        current_service_key, current_service_tag = osparc_image_key.split(":")
        involved_key = _assemble_key(
            service_key=current_service_key, service_tag=current_service_tag
        )
        reverse_mapping[involved_key] = compose_service_key

        simcore_service_labels: SimcoreServiceLabels = (
            await director_v0_client.get_service_labels(
                service=ServiceKeyVersion(
                    key=current_service_key, version=current_service_tag
                )
            )
        )
        docker_image_name_by_services[involved_key] = simcore_service_labels

    if len(reverse_mapping) != len(docker_image_name_by_services):
        message = (
            f"Extracting labels for services in '{image}' could not fill "
            f"reverse_mapping={reverse_mapping}; "
            f"docker_image_name_by_services={docker_image_name_by_services}"
        )
        log.error(message)
        raise DynamicSidecarError(msg=message)

    return remap_to_compose_spec_key()


def _add_compose_destination_containers_to_settings_entries(
    settings: SimcoreServiceSettingsLabel, destination_containers: list[str]
) -> list[SimcoreServiceSettingLabelEntry]:
    def _inject_destination_container(
        item: SimcoreServiceSettingLabelEntry,
    ) -> SimcoreServiceSettingLabelEntry:
        item.set_destination_containers(destination_containers)
        return item

    return [_inject_destination_container(x) for x in settings]


def _merge_resources_in_settings(
    settings: deque[SimcoreServiceSettingLabelEntry],
    service_resources: ServiceResourcesDict,
    *,
    placement_substitutions: dict[str, DockerPlacementConstraint],
) -> deque[SimcoreServiceSettingLabelEntry]:
    """All oSPARC services which have defined resource requirements will be added"""
    log.debug("MERGING\n%s\nAND\n%s", f"{settings=}", f"{service_resources}")

    result: deque[SimcoreServiceSettingLabelEntry] = deque()

    entry: SimcoreServiceSettingLabelEntry
    for entry in settings:
        if entry.name == "Resources" and entry.setting_type == "Resources":
            # skipping resources
            continue
        result.append(entry)

    # merge all resources
    empty_resource_entry: SimcoreServiceSettingLabelEntry = (
        SimcoreServiceSettingLabelEntry.model_validate(
            {
                "name": "Resources",
                "type": "Resources",
                "value": {
                    "Limits": {"NanoCPUs": 0, "MemoryBytes": 0},
                    "Reservations": {
                        "NanoCPUs": 0,
                        "MemoryBytes": 0,
                        "GenericResources": [],
                    },
                },
            }
        )
    )

    for image_resources in service_resources.values():
        for resource_name, resource_value in image_resources.resources.items():
            if resource_name == "CPU":
                empty_resource_entry.value["Limits"]["NanoCPUs"] += int(
                    float(resource_value.limit) * GIGA
                )
                empty_resource_entry.value["Reservations"]["NanoCPUs"] += int(
                    float(resource_value.reservation) * GIGA
                )
            elif resource_name == "RAM":
                empty_resource_entry.value["Limits"][
                    "MemoryBytes"
                ] += resource_value.limit
                empty_resource_entry.value["Reservations"][
                    "MemoryBytes"
                ] += resource_value.reservation
            else:  # generic resources
                if resource_name in placement_substitutions:
                    # NOTE: placement constraint will be used in favour of this generic resource
                    continue
                generic_resource = {
                    "DiscreteResourceSpec": {
                        "Kind": resource_name,
                        # NOTE: when dealing with generic resources only `reservation`
                        # is set, `limit` is 0
                        "Value": resource_value.reservation,
                    }
                }
                empty_resource_entry.value["Reservations"]["GenericResources"].extend(
                    [generic_resource]
                )
    # since some services do not define CPU limitations, by default 0.1% CPU is assigned
    # ensuring limit is at least 1.0 CPUs otherwise the dynamic-sidecar is not able to work
    # properly
    empty_resource_entry.value["Limits"]["NanoCPUs"] = max(
        empty_resource_entry.value["Limits"]["NanoCPUs"], CPU_100_PERCENT
    )
    empty_resource_entry.value["Limits"]["MemoryBytes"] = max(
        empty_resource_entry.value["Limits"]["MemoryBytes"], MEMORY_1GB
    )

    result.append(empty_resource_entry)

    return result


def _patch_target_service_into_env_vars(
    settings: deque[SimcoreServiceSettingLabelEntry],
) -> deque[SimcoreServiceSettingLabelEntry]:
    """NOTE: this method will modify settings in place"""

    def _format_env_var(env_var: str, destination_container: list[str]) -> str:
        var_name, var_payload = env_var.split("=")
        json_encoded = json.dumps(
            {"destination_containers": destination_container, "env_var": var_payload}
        )
        return f"{var_name}={json_encoded}"

    entry: SimcoreServiceSettingLabelEntry
    for entry in settings:
        if entry.name == "env" and entry.setting_type == "string":
            # process entry
            list_of_env_vars = entry.value if entry.value else []

            destination_containers: list[str] = entry.get_destination_containers()

            # transforms settings defined environment variables
            # from `ENV_VAR=PAYLOAD`
            # to   `ENV_VAR={"destination_container": ["destination_container"], "env_var": "PAYLOAD"}`
            entry.value = [
                _format_env_var(x, destination_containers) for x in list_of_env_vars
            ]

    return settings


def _get_boot_options(
    service_labels: SimcoreServiceLabels,
) -> dict[EnvVarKey, BootOption] | None:
    as_dict = service_labels.model_dump()
    boot_options_encoded = as_dict.get("io.simcore.boot-options", None)
    if boot_options_encoded is None:
        return None

    boot_options = json.loads(boot_options_encoded)["boot-options"]
    log.debug("got boot_options=%s", boot_options)
    return {k: BootOption.model_validate(v) for k, v in boot_options.items()}


def _assemble_env_vars_for_boot_options(
    boot_options: dict[EnvVarKey, BootOption],
    service_user_selection_boot_options: dict[EnvVarKey, str],
) -> SimcoreServiceSettingsLabel:
    env_vars: deque[str] = deque()
    for env_var_key, boot_option in boot_options.items():
        # fetch value selected by the user or use default if not present
        value = service_user_selection_boot_options.get(
            env_var_key, boot_option.default
        )
        env_var_name = f"{BOOT_OPTION_PREFIX}_{env_var_key}".upper()
        env_vars.append(f"{env_var_name}={value}")

    return SimcoreServiceSettingsLabel(
        root=[
            SimcoreServiceSettingLabelEntry(
                name="env", type="string", value=list(env_vars)
            )
        ]
    )


async def get_labels_for_involved_services(
    director_v0_client: DirectorV0Client,
    service_key: ServiceKey,
    service_tag: ServiceVersion,
) -> dict[str, SimcoreServiceLabels]:
    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(key=service_key, version=service_tag)
        )
    )
    log.info(
        "image=%s, tag=%s, labels=%s", service_key, service_tag, simcore_service_labels
    )

    # paths_mapping express how to map dynamic-sidecar paths to the compose-spec volumes
    # where the service expects to find its certain folders

    labels_for_involved_services: dict[
        str, SimcoreServiceLabels
    ] = await _extract_osparc_involved_service_labels(
        director_v0_client=director_v0_client,
        service_key=service_key,
        service_tag=service_tag,
        service_labels=simcore_service_labels,
    )
    logging.info("labels_for_involved_services=%s", labels_for_involved_services)
    return labels_for_involved_services


async def merge_settings_before_use(
    director_v0_client: DirectorV0Client,
    *,
    service_key: ServiceKey,
    service_tag: ServiceVersion,
    service_user_selection_boot_options: dict[EnvVarKey, str],
    service_resources: ServiceResourcesDict,
    placement_substitutions: dict[str, DockerPlacementConstraint],
) -> SimcoreServiceSettingsLabel:
    labels_for_involved_services = await get_labels_for_involved_services(
        director_v0_client=director_v0_client,
        service_key=service_key,
        service_tag=service_tag,
    )

    settings: deque[SimcoreServiceSettingLabelEntry] = deque()

    boot_options_settings_env_vars: SimcoreServiceSettingsLabel | None = None
    # search for boot options first and inject to all containers
    for service_labels in labels_for_involved_services.values():
        labels_boot_options = _get_boot_options(service_labels)
        if labels_boot_options:
            # create a new setting from SimcoreServiceSettingsLabel as env var
            boot_options_settings_env_vars = _assemble_env_vars_for_boot_options(
                labels_boot_options, service_user_selection_boot_options
            )
            settings.extend(
                _add_compose_destination_containers_to_settings_entries(
                    settings=boot_options_settings_env_vars,
                    destination_containers=list(labels_for_involved_services.keys()),
                )
            )
            break

    # merge the settings from the all the involved services
    for compose_spec_key, service_labels in labels_for_involved_services.items():
        service_settings: SimcoreServiceSettingsLabel = cast(
            SimcoreServiceSettingsLabel, service_labels.settings
        )
        settings.extend(
            # inject compose spec key, used to target container specific services
            _add_compose_destination_containers_to_settings_entries(
                settings=service_settings, destination_containers=[compose_spec_key]
            )
        )

    settings = _merge_resources_in_settings(
        settings, service_resources, placement_substitutions=placement_substitutions
    )
    settings = _patch_target_service_into_env_vars(settings)

    return SimcoreServiceSettingsLabel.model_validate(settings)


__all__ = ["merge_settings_before_use", "update_service_params_from_settings"]
