from copy import deepcopy
from typing import Any

from models_library.generated_models.docker_rest_api import ServiceSpec
from models_library.services_resources import ResourcesDict, ResourceValue

_DOCKER_TO_OSPARC_RESOURCE_ATTR = {"Limits": "limit", "Reservations": "reservation"}
_DOCKER_TO_OSPARC_RESOURCE_MAP = {"NanoCPUs": "CPU", "MemoryBytes": "RAM"}
_DOCKER_TO_OSPARC_RESOURCE_CONVERTER = {"NanoCPUs": 1 / (10**9), "MemoryBytes": 1}


def parse_generic_resource(generic_resources: list[Any]) -> ResourcesDict:
    service_resources: ResourcesDict = {}
    for res in generic_resources:
        if not isinstance(res, dict):
            continue

        if named_resource_spec := res.get("NamedResourceSpec"):
            if named_resource_spec.get("Value") is None:
                continue
            service_resources.setdefault(
                named_resource_spec["Kind"],
                ResourceValue(
                    limit=named_resource_spec["Value"],
                    reservation=named_resource_spec["Value"],
                ),
            ).reservation = named_resource_spec["Value"]
        if discrete_resource_spec := res.get("DiscreteResourceSpec"):
            if discrete_resource_spec.get("Value") is None:
                continue
            service_resources.setdefault(
                discrete_resource_spec["Kind"],
                ResourceValue(
                    limit=discrete_resource_spec["Value"],
                    reservation=discrete_resource_spec["Value"],
                ),
            ).reservation = discrete_resource_spec["Value"]
    return service_resources


def merge_service_resources_with_user_specs(
    service_resources: ResourcesDict, user_specific_spec: ServiceSpec
) -> ResourcesDict:
    if (
        not user_specific_spec.TaskTemplate
        or not user_specific_spec.TaskTemplate.Resources
    ):
        return service_resources
    user_specific_resources = user_specific_spec.dict(
        include={"TaskTemplate": {"Resources"}}
    )["TaskTemplate"]["Resources"]

    merged_resources = deepcopy(service_resources)
    for docker_res_type, osparc_res_attr in _DOCKER_TO_OSPARC_RESOURCE_ATTR.items():
        if user_specific_resources.get(docker_res_type) is None:
            continue
        for res_name, res_value in user_specific_resources[docker_res_type].items():
            # res_name: NanoCPUs, MemoryBytes, Pids, GenericResources
            if res_value is None:
                continue
            if res_name == "GenericResources":
                # special case here
                merged_resources |= parse_generic_resource(res_value)
                continue
            if res_name not in _DOCKER_TO_OSPARC_RESOURCE_MAP:
                continue
            if _DOCKER_TO_OSPARC_RESOURCE_MAP[res_name] in merged_resources:
                # upgrade
                merged_resources[_DOCKER_TO_OSPARC_RESOURCE_MAP[res_name]].__setattr__(
                    osparc_res_attr,
                    res_value * _DOCKER_TO_OSPARC_RESOURCE_CONVERTER[res_name],
                )
            else:
                merged_resources[
                    _DOCKER_TO_OSPARC_RESOURCE_MAP[res_name]
                ] = ResourceValue(
                    limit=res_value * _DOCKER_TO_OSPARC_RESOURCE_CONVERTER[res_name],
                    reservation=res_value
                    * _DOCKER_TO_OSPARC_RESOURCE_CONVERTER[res_name],
                )

    return merged_resources
