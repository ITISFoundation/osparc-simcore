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
        not user_specific_spec.task_template
        or not user_specific_spec.task_template.resources
    ):
        return service_resources

    assert "task_template" in user_specific_spec.model_fields  # nosec

    user_specific_resources = user_specific_spec.model_dump(
        include={"task_template": {"resources"}}, by_alias=True
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

            scale = _DOCKER_TO_OSPARC_RESOURCE_CONVERTER[res_name]
            key = _DOCKER_TO_OSPARC_RESOURCE_MAP[res_name]
            if key in merged_resources:
                # updates.
                # NOTE: do not use assignment!
                # SEE test_reservation_is_cap_by_limit_on_assigment_pydantic_2_bug
                data = merged_resources[key].model_dump()
                data[osparc_res_attr] = res_value * scale
                merged_resources[key] = ResourceValue(**data)
            else:
                # constructs
                merged_resources[key] = ResourceValue(
                    limit=res_value * scale,
                    reservation=res_value * scale,
                )

    return merged_resources
