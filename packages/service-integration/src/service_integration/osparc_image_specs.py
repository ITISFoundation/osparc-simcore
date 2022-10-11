""" Defines different Image Specification (image-spec) for osparc user services

"""


from typing import Optional

from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    Service,
)

from .context import IntegrationContext
from .osparc_config import DockerComposeOverwriteCfg, MetaConfig, RuntimeConfig


def create_image_spec(
    integration_context: IntegrationContext,
    meta_cfg: MetaConfig,
    docker_compose_overwrite_cfg: DockerComposeOverwriteCfg,
    runtime_cfg: Optional[RuntimeConfig] = None,
    *,
    extra_labels: dict[str, str] = {},
    **_context
) -> ComposeSpecification:
    """Creates the image-spec provided the osparc-config and a given context (e.g. development)

    - the image-spec simplifies building an image to ``docker-compose build``
    """

    labels = {**extra_labels, **meta_cfg.to_labels_annotations()}
    if runtime_cfg:
        labels.update(runtime_cfg.to_labels_annotations())

    service_name = meta_cfg.service_name()
    context = docker_compose_overwrite_cfg.services[service_name].build.context
    docker_compose_overwrite_cfg.services[service_name].build.context = (
        context if context else "./"
    )
    docker_compose_overwrite_cfg.services[service_name].build.labels = labels

    overwrite_options = docker_compose_overwrite_cfg.services[service_name].build.dict(
        exclude_none=True
    )

    build_spec = BuildItem(**overwrite_options)

    compose_spec = ComposeSpecification(
        version=integration_context.COMPOSE_VERSION,
        services={
            service_name: Service(
                image=meta_cfg.image_name(integration_context), build=build_spec
            )
        },
    )
    return compose_spec
