""" Defines different Image Specification (image-spec) for osparc user services

"""


from typing import Dict, Optional

from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    Service,
)

from .osparc_config import IOSpecification, ServiceSpecification


def create_image_spec(
    io_spec: IOSpecification,
    service_spec: Optional[ServiceSpecification] = None,
    *,
    extra_labels: Dict[str, str] = {}
) -> ComposeSpecification:
    """produces image-specification provided the osparc-config

    - Can be executed with ``docker-compose build``
    """

    labels = {**extra_labels, **io_spec.to_labels_annotations()}
    if service_spec:
        labels.update(service_spec.to_labels_annotations())

    build_spec = BuildItem(
        context="./",
        dockerfile="docker/Dockerfile",
        labels=labels,
        args={"VERSION": io_spec.version},
    )

    compose_spec = ComposeSpecification(
        version="3.7",
        services={io_spec.name: Service(image=io_spec.image_name(), build=build_spec)},
    )
    return compose_spec
