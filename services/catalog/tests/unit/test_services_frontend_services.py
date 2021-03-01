# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from simcore_service_catalog.models.schemas.services import (
    ServiceDockerData,
    ServiceOut,
)
from simcore_service_catalog.services.frontend_services import (
    create_file_picker_service,
    create_node_group_service,
)


def test_create_file_picker():

    image_metadata = create_file_picker_service()
    assert isinstance(image_metadata, ServiceDockerData)

    assert (
        not image_metadata.inputs and image_metadata.outputs
    ), "Expected a source node"

    service = ServiceOut.parse_obj(image_metadata.dict(by_alias=True))


def tests_create_node_group():
    image_metadata = create_node_group_service()
    assert isinstance(image_metadata, ServiceDockerData)

    assert (
        not image_metadata.inputs and image_metadata.outputs
    ), "Expected a source node"

    service = ServiceOut.parse_obj(image_metadata.dict(by_alias=True))
