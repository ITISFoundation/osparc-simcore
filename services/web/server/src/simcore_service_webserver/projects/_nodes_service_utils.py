from models_library.services_resources import ServiceResourcesDict

from .exceptions import (
    InvalidContainerInResourcesSpecsError,
    InvalidImageInResourcesSpecsError,
)


def validate_new_service_resources(
    resources: ServiceResourcesDict, *, new_resources: ServiceResourcesDict
) -> None:
    """validate new_resources can be applied on resources

    Raises:
        ProjectNodeResourcesInvalidError
    """

    # NOTE: ServiceResourcesDict is made of either {"container": {"image": "simcore/services/...", "resources":{}}}
    # or {"jupyter-smash": {"image": "simcore/services/...", "resources": {}}}
    # the docker container entries shall be contained in the current resources
    for container_name, container_resources in new_resources.items():
        if container_name not in resources:
            raise InvalidContainerInResourcesSpecsError(
                container_name=container_name, resource_keys=tuple(resources.keys())
            )
        # now check the image names fit
        if container_resources.image != resources[container_name].image:
            raise InvalidImageInResourcesSpecsError(
                image_name=container_resources.image,
                container_name=container_name,
                expected_image=resources[container_name].image,
            )


def set_reservation_same_as_limit(
    resources: ServiceResourcesDict,
) -> None:
    for container_resources in resources.values():
        container_resources.set_reservation_same_as_limit()
