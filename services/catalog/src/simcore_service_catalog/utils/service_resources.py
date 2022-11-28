from copy import deepcopy

from models_library.generated_models.docker_rest_api import ServiceSpec
from models_library.services_resources import ResourcesDict, ResourceValue


def merge_service_resources_with_user_specs(
    service_resources: ResourcesDict, user_specific_spec: ServiceSpec
) -> ResourcesDict:
    merged_resources = deepcopy(service_resources)
    if user_specific_spec.TaskTemplate and user_specific_spec.TaskTemplate.Resources:
        user_specific_resources = user_specific_spec.TaskTemplate.Resources
        if user_specific_resources.Limits:
            if user_specific_resources.Limits.NanoCPUs:
                merged_resources["CPU"].limit = (
                    user_specific_resources.Limits.NanoCPUs / 10**9
                )
            if user_specific_resources.Limits.MemoryBytes:
                merged_resources[
                    "RAM"
                ].limit = user_specific_resources.Limits.MemoryBytes
        if user_specific_resources.Reservations:
            if user_specific_resources.Reservations.NanoCPUs:
                merged_resources["CPU"].reservation = (
                    user_specific_resources.Reservations.NanoCPUs / 10**9
                )
            if user_specific_resources.Reservations.MemoryBytes:
                merged_resources[
                    "RAM"
                ].reservation = user_specific_resources.Reservations.MemoryBytes
            if user_specific_resources.Reservations.GenericResources:
                for (
                    generic_resource
                ) in user_specific_resources.Reservations.GenericResources.__root__:
                    if (
                        generic_resource.DiscreteResourceSpec
                        and generic_resource.DiscreteResourceSpec.Kind
                        and generic_resource.DiscreteResourceSpec.Value
                    ):
                        merged_resources[
                            generic_resource.DiscreteResourceSpec.Kind
                        ] = ResourceValue(
                            limit=generic_resource.DiscreteResourceSpec.Value,
                            reservation=generic_resource.DiscreteResourceSpec.Value,
                        )
                    if (
                        generic_resource.NamedResourceSpec
                        and generic_resource.NamedResourceSpec.Kind
                        and generic_resource.NamedResourceSpec.Value
                    ):
                        merged_resources[
                            generic_resource.NamedResourceSpec.Kind
                        ] = ResourceValue(
                            limit=generic_resource.NamedResourceSpec.Value,
                            reservation=generic_resource.NamedResourceSpec.Value,
                        )

    return merged_resources
