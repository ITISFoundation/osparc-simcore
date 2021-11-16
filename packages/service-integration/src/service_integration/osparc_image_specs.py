""" Defines different Image Specification (image-spec) for osparc user services

"""


from typing import Dict, Optional

from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    Service,
)

from .osparc_config import MetaConfig, RuntimeConfig


def create_image_spec(
    meta_cfg: MetaConfig,
    runtime_cfg: Optional[RuntimeConfig] = None,
    *,
    extra_labels: Dict[str, str] = {},
    **_context
) -> ComposeSpecification:
    """Creates the image-spec provided the osparc-config and a given context (e.g. development)

    - the image-spec simplifies building an image to ``docker-compose build``
    """
    # TODO: context still not implemented

    labels = {**extra_labels, **meta_cfg.to_labels_annotations()}
    if runtime_cfg:
        labels.update(runtime_cfg.to_labels_annotations())

    build_spec = BuildItem(
        context="./",
        # TODO: tool to find stardard location of file, get from config or query user
        dockerfile="docker/Dockerfile",
        labels=labels,
        args={"VERSION": meta_cfg.version},
    )

    compose_spec = ComposeSpecification(
        version="3.7",  # TODO: how compatibility is guaranteed? Sync with docker-compose version required in this repo!!
        services={
            meta_cfg.service_name(): Service(
                image=meta_cfg.image_name(), build=build_spec
            )
        },
    )
    return compose_spec
