import json
import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional, cast

from models_library.boot_options import BootOption, EnvVarKey
from models_library.service_settings_labels import (
    ComposeSpecLabel,
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
from servicelib.docker_compose import (
    MATCH_IMAGE_END,
    MATCH_IMAGE_START,
    MATCH_SERVICE_VERSION,
)

from ....api.dependencies.director_v0 import DirectorV0Client
from ..errors import DynamicSidecarError

BOOT_OPTION_PREFIX = "DY_BOOT_OPTION"


log = logging.getLogger(__name__)


def _parse_mount_settings(settings: List[Dict]) -> List[Dict]:
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


def _parse_env_settings(settings: List[str]) -> Dict:
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


# pylint: disable=too-many-branches
def update_service_params_from_settings(
    labels_service_settings: SimcoreServiceSettingsLabel,
    create_service_params: Dict[str, Any],
) -> None:
    for param in labels_service_settings:
        param: SimcoreServiceSettingLabelEntry = param
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

        # publishing port on the ingress network.
        elif param.name == "ports" and param.setting_type == "int":  # backward comp
            create_service_params["labels"]["port"] = create_service_params["labels"][
                "service_port"
            ] = str(param.value)
        # REST-API compatible
        elif param.setting_type == "EndpointSpec":
            if "Ports" in param.value:
                if (
                    isinstance(param.value["Ports"], list)
                    and "TargetPort" in param.value["Ports"][0]
                ):
                    create_service_params["labels"]["port"] = create_service_params[
                        "labels"
                    ]["service_port"] = str(param.value["Ports"][0]["TargetPort"])

        # placement constraints
        elif param.name == "constraints":  # python-API compatible
            create_service_params["task_template"]["Placement"][
                "Constraints"
            ] += param.value
        elif param.setting_type == "Constraints":  # REST-API compatible
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
            mount_settings: List[Dict] = _parse_mount_settings(param.value)
            if mount_settings:
                create_service_params["task_template"]["ContainerSpec"][
                    "Mounts"
                ].extend(mount_settings)

    container_spec = create_service_params["task_template"]["ContainerSpec"]
    # set labels for CPU and Memory limits
    container_spec["Labels"]["nano_cpus_limit"] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["NanoCPUs"]
    )
    container_spec["Labels"]["mem_limit"] = str(
        create_service_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )


def _assemble_key(service_key: str, service_tag: str) -> str:
    return f"{service_key}:{service_tag}"


async def _extract_osparc_involved_service_labels(
    director_v0_client: DirectorV0Client,
    service_key: str,
    service_tag: str,
    service_labels: SimcoreServiceLabels,
) -> Dict[str, SimcoreServiceLabels]:
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
    docker_image_name_by_services: Dict[str, SimcoreServiceLabels] = {
        _default_key: service_labels
    }
    # maps form image_name to compose_spec key
    reverse_mapping: Dict[str, str] = {_default_key: DEFAULT_SINGLE_SERVICE_NAME}

    def remap_to_compose_spec_key() -> Dict[str, str]:
        # remaps from image_name as key to compose_spec key
        return {reverse_mapping[k]: v for k, v in docker_image_name_by_services.items()}

    compose_spec: Optional[ComposeSpecLabel] = cast(
        ComposeSpecLabel, service_labels.compose_spec
    )
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
        raise DynamicSidecarError(message)

    return remap_to_compose_spec_key()


def _add_compose_destination_container_to_settings_entries(
    settings: SimcoreServiceSettingsLabel, destination_container: str
) -> List[SimcoreServiceSettingLabelEntry]:
    def _inject_destination_container(
        item: SimcoreServiceSettingLabelEntry,
    ) -> SimcoreServiceSettingLabelEntry:
        # pylint: disable=protected-access
        item._destination_container = destination_container
        return item

    return [_inject_destination_container(x) for x in settings]


def _merge_resources_in_settings(
    settings: Deque[SimcoreServiceSettingLabelEntry],
    service_resources: ServiceResourcesDict,
) -> Deque[SimcoreServiceSettingLabelEntry]:
    """All oSPARC services which have defined resource requirements will be added"""
    log.debug("MERGING\n%s\nAND\n%s", f"{settings=}", f"{service_resources}")

    result: Deque[SimcoreServiceSettingLabelEntry] = deque()

    for entry in settings:
        entry: SimcoreServiceSettingLabelEntry = entry
        if entry.name == "Resources" and entry.setting_type == "Resources":
            # skipping resources
            continue
        result.append(entry)

    # merge all resources
    empty_resource_entry: SimcoreServiceSettingLabelEntry = (
        SimcoreServiceSettingLabelEntry.parse_obj(
            dict(
                name="Resources",
                type="Resources",
                value={
                    "Limits": {"NanoCPUs": 0, "MemoryBytes": 0},
                    "Reservations": {
                        "NanoCPUs": 0,
                        "MemoryBytes": 0,
                        "GenericResources": [],
                    },
                },
            )
        )
    )

    for _, image_resources in service_resources.items():
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
    settings: Deque[SimcoreServiceSettingLabelEntry],
) -> Deque[SimcoreServiceSettingLabelEntry]:
    """NOTE: this method will modify settings in place"""

    def _format_env_var(env_var: str, destination_container: str) -> str:
        var_name, var_payload = env_var.split("=")
        json_encoded = json.dumps(
            dict(destination_container=destination_container, env_var=var_payload)
        )
        return f"{var_name}={json_encoded}"

    for entry in settings:
        entry: SimcoreServiceSettingLabelEntry = entry
        if entry.name == "env" and entry.setting_type == "string":
            # process entry
            list_of_env_vars = entry.value if entry.value else []

            # pylint: disable=protected-access
            destination_container = entry._destination_container

            # transforms settings defined environment variables
            # from `ENV_VAR=PAYLOAD`
            # to   `ENV_VAR={"destination_container": "destination_container", "env_var": "PAYLOAD"}`
            entry.value = [
                _format_env_var(x, destination_container) for x in list_of_env_vars
            ]

    return settings


def _get_boot_options(
    service_labels: SimcoreServiceLabels,
) -> Optional[Dict[EnvVarKey, BootOption]]:
    as_dict = service_labels.dict()
    boot_options_encoded = as_dict.get("io.simcore.boot-options", None)
    if boot_options_encoded is None:
        return None

    boot_options = json.loads(boot_options_encoded)["boot-options"]
    log.debug("got boot_options=%s", boot_options)
    return {k: BootOption.parse_obj(v) for k, v in boot_options.items()}


def _assemble_env_vars_for_boot_options(
    boot_options: Dict[EnvVarKey, BootOption],
    service_user_selection_boot_options: Dict[EnvVarKey, str],
) -> SimcoreServiceSettingsLabel:

    env_vars: Deque[str] = deque()
    for env_var_key, boot_option in boot_options.items():
        # fetch value selected by the user or use default if not present
        value = service_user_selection_boot_options.get(
            env_var_key, boot_option.default
        )
        env_var_name = f"{BOOT_OPTION_PREFIX}_{env_var_key}".upper()
        env_vars.append(f"{env_var_name}={value}")

    return SimcoreServiceSettingsLabel(
        __root__=[
            SimcoreServiceSettingLabelEntry(
                name="env", type="string", value=list(env_vars)
            )
        ]
    )


async def get_labels_for_involved_services(
    director_v0_client: DirectorV0Client, service_key: str, service_tag: str
) -> Dict[str, SimcoreServiceLabels]:
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

    labels_for_involved_services: Dict[
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
    service_key: str,
    service_tag: str,
    service_user_selection_boot_options: Dict[EnvVarKey, str],
    service_resources: ServiceResourcesDict,
) -> SimcoreServiceSettingsLabel:
    labels_for_involved_services = await get_labels_for_involved_services(
        director_v0_client=director_v0_client,
        service_key=service_key,
        service_tag=service_tag,
    )

    # merge the settings from the all the involved services
    settings: Deque[SimcoreServiceSettingLabelEntry] = deque()  # TODO: fix typing here
    for compose_spec_key, service_labels in labels_for_involved_services.items():
        service_settings: SimcoreServiceSettingsLabel = cast(
            SimcoreServiceSettingsLabel, service_labels.settings
        )

        settings.extend(
            # inject compose spec key, used to target container specific services
            _add_compose_destination_container_to_settings_entries(
                settings=service_settings, destination_container=compose_spec_key
            )
        )

        # inject boot options as env vars
        labels_boot_options = _get_boot_options(service_labels)
        if labels_boot_options:
            # create a new setting from SimcoreServiceSettingsLabel as env var to pass to target container
            boot_options_settings_env_vars = _assemble_env_vars_for_boot_options(
                labels_boot_options, service_user_selection_boot_options
            )
            settings.extend(
                # inject compose spec key, used to target container specific services
                _add_compose_destination_container_to_settings_entries(
                    settings=boot_options_settings_env_vars,
                    destination_container=compose_spec_key,
                )
            )

    settings = _merge_resources_in_settings(settings, service_resources)
    settings = _patch_target_service_into_env_vars(settings)

    return SimcoreServiceSettingsLabel.parse_obj(settings)


__all__ = ["merge_settings_before_use", "update_service_params_from_settings"]
