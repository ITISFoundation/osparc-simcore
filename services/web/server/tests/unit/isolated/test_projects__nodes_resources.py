from copy import deepcopy

import pytest
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import parse_obj_as
from simcore_service_webserver.projects._nodes_utils import (
    validate_new_service_resources,
)
from simcore_service_webserver.projects.exceptions import (
    ProjectNodeResourcesInvalidError,
)


@pytest.mark.parametrize(
    "resources",
    [
        parse_obj_as(ServiceResourcesDict, example)
        for example in ServiceResourcesDictHelpers.Config.schema_extra["examples"]
    ],
)
def test_check_can_update_service_resources_with_same_does_not_raise(
    resources: ServiceResourcesDict,
):
    new_resources = deepcopy(resources)
    validate_new_service_resources(resources, new_resources=new_resources)


@pytest.mark.parametrize(
    "resources",
    [
        parse_obj_as(ServiceResourcesDict, example)
        for example in ServiceResourcesDictHelpers.Config.schema_extra["examples"]
    ],
)
def test_check_can_update_service_resources_with_invalid_container_name_raises(
    resources: ServiceResourcesDict,
):
    new_resources = {
        f"{resource_name}-invalid-name": resource_data
        for resource_name, resource_data in resources.items()
    }

    with pytest.raises(ProjectNodeResourcesInvalidError, match="invalid-name"):
        validate_new_service_resources(resources, new_resources=new_resources)


@pytest.mark.parametrize(
    "resources",
    [
        parse_obj_as(ServiceResourcesDict, example)
        for example in ServiceResourcesDictHelpers.Config.schema_extra["examples"]
    ],
)
def test_check_can_update_service_resources_with_invalid_image_name_raises(
    resources: ServiceResourcesDict,
):
    new_resources = {
        resource_name: resource_data.copy(update={"image": "some-invalid-image-name"})
        for resource_name, resource_data in resources.items()
    }
    with pytest.raises(
        ProjectNodeResourcesInvalidError, match="some-invalid-image-name"
    ):
        validate_new_service_resources(resources, new_resources=new_resources)
