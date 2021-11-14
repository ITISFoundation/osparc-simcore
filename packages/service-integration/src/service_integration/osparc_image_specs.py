""" Defines different Image Specification (image-spec) for osparc user services

"""


from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    Service,
)

from .osparc_config import IOSpecification, ServiceSpecification


def create_image_spec(
    io_spec: IOSpecification, service_spec: ServiceSpecification
) -> ComposeSpecification:
    """produces image-specification provided the osparc-config

    - Can be executed with ``docker-compose build``
    """

    build_spec = BuildItem(
        context=".",
        dockerfile="Dockerfile",
        labels={
            **io_spec.to_labels_annotations(),
            **service_spec.to_labels_annotations(),
        },
    )

    compose_spec = ComposeSpecification(
        version="3.7",
        services={io_spec.name: Service(image=io_spec.image_name(), build=build_spec)},
    )
    return compose_spec
