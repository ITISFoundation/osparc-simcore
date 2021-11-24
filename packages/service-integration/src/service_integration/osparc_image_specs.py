""" Defines different Image Specification (image-spec) for osparc user services

"""


from typing import Dict, Optional

from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    Service,
)

from .context import IntegrationContext
from .osparc_config import MetaConfig, ProjectConfig, RuntimeConfig


def create_image_spec(
    integration_context: IntegrationContext,
    project_cfg: ProjectConfig,
    meta_cfg: MetaConfig,
    runtime_cfg: Optional[RuntimeConfig] = None,
    *,
    extra_labels: Dict[str, str] = {},
) -> ComposeSpecification:
    """Creates the image-spec provided the osparc-config and a given context (e.g. development)

    - the image-spec simplifies building an image to ``docker-compose build``
    """

    labels = {**extra_labels, **meta_cfg.to_labels_annotations()}
    if runtime_cfg:
        labels.update(runtime_cfg.to_labels_annotations())

    build_spec = BuildItem(
        context="./",
        dockerfile=f"{project_cfg.dockerfile_path}",
        labels=labels,
        args={"VERSION": meta_cfg.version},
    )

    compose_spec = ComposeSpecification(
        version="3.7",  # TODO: how compatibility is guaranteed? Sync with docker-compose version required in this repo!!
        services={
            meta_cfg.service_name(): Service(
                image=meta_cfg.image_name(integration_context), build=build_spec
            )
        },
    )
    return compose_spec
