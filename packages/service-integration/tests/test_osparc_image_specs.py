# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel
from service_integration.compose_spec_model import BuildItem, Service
from service_integration.context import IntegrationContext
from service_integration.osparc_config import (
    MetaConfig,
    DockerComposeOverwriteCfg,
    RuntimeConfig,
)
from service_integration.osparc_image_specs import create_image_spec


@pytest.fixture
def integration_context() -> IntegrationContext:
    return IntegrationContext()


def test_create_image_spec_impl(
    tests_data_dir: Path, integration_context: IntegrationContext
):
    # have image spec  -> assemble build part of the compose-spec -> ready to build with `docker-compose build`
    # image-spec for devel, prod, ...

    # load & parse osparc configs
    docker_compose_overwrite_cfg = DockerComposeOverwriteCfg.from_yaml(
        tests_data_dir / "docker-compose.overwrite.yml"
    )
    meta_cfg = MetaConfig.from_yaml(tests_data_dir / "metadata-dynamic.yml")
    runtime_cfg = RuntimeConfig.from_yaml(tests_data_dir / "runtime.yml")

    # assemble docker-compose
    build_spec = BuildItem(
        context=".",
        dockerfile="Dockerfile",
        labels={
            **meta_cfg.to_labels_annotations(),
            **runtime_cfg.to_labels_annotations(),
        },
    )

    compose_spec = create_image_spec(
        integration_context, meta_cfg, docker_compose_overwrite_cfg, runtime_cfg
    )
    assert compose_spec.services is not None
    assert isinstance(compose_spec.services, dict)

    service_name = list(compose_spec.services.keys())[0]
    # pylint: disable=unsubscriptable-object
    assert isinstance(compose_spec.services[service_name], Service)
    build_spec = compose_spec.services[service_name].build
    assert build_spec
    assert isinstance(build_spec, BaseModel)

    print(build_spec.json(exclude_unset=True, indent=2))
    print(yaml.safe_dump(compose_spec.dict(exclude_unset=True), sort_keys=False))
