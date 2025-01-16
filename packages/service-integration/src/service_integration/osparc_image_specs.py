""" Defines different Image Specification (image-spec) for osparc user services

"""

from typing import Any

from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    ListOrDict,
    Service,
)

from .osparc_config import DockerComposeOverwriteConfig, MetadataConfig, RuntimeConfig
from .settings import AppSettings


def create_image_spec(
    settings: AppSettings,
    meta_cfg: MetadataConfig,
    docker_compose_overwrite_cfg: DockerComposeOverwriteConfig,
    runtime_cfg: RuntimeConfig | None = None,
    *,
    extra_labels: dict[str, str] | None = None,
    **_context
) -> ComposeSpecification:
    """Creates the image-spec provided the osparc-config and a given context (e.g. development)

    - the image-spec simplifies building an image to ``docker compose build``
    """
    labels = meta_cfg.to_labels_annotations()
    if extra_labels:
        labels.update(extra_labels)
    if runtime_cfg:
        labels.update(runtime_cfg.to_labels_annotations())

    service_name = meta_cfg.service_name()

    assert docker_compose_overwrite_cfg.services  # nosec

    build = docker_compose_overwrite_cfg.services[service_name].build
    assert isinstance(build, BuildItem)  # nosec
    if not build.context:
        build.context = "./"

    build.labels = ListOrDict(root=labels)

    overwrite_options = build.model_dump(exclude_none=True, serialize_as_any=True)
    build_spec = BuildItem(**overwrite_options)

    service_kwargs: dict[str, Any] = {
        "image": meta_cfg.image_name(settings),
        "build": build_spec,
    }
    if docker_compose_overwrite_cfg.services[service_name].depends_on:
        service_kwargs["depends_on"] = docker_compose_overwrite_cfg.services[
            service_name
        ].depends_on

    return ComposeSpecification(
        version=settings.COMPOSE_VERSION,
        services={service_name: Service(**service_kwargs)},
    )
