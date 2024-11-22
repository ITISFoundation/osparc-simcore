# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import hashlib
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel
from service_integration.compose_spec_model import BuildItem, Service
from service_integration.osparc_config import (
    DockerComposeOverwriteConfig,
    MetadataConfig,
    RuntimeConfig,
)
from service_integration.osparc_image_specs import create_image_spec
from service_integration.settings import AppSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings()


def test_create_image_spec_impl(tests_data_dir: Path, settings: AppSettings):
    # have image spec  -> assemble build part of the compose-spec -> ready to build with `docker-compose build`
    # image-spec for devel, prod, ...

    # load & parse osparc configs
    docker_compose_overwrite_cfg = DockerComposeOverwriteConfig.from_yaml(
        tests_data_dir / "docker-compose.overwrite.yml"
    )
    meta_cfg = MetadataConfig.from_yaml(tests_data_dir / "metadata-dynamic.yml")
    runtime_cfg = RuntimeConfig.from_yaml(tests_data_dir / "runtime.yml")
    assert runtime_cfg.callbacks_mapping is not None

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
        settings, meta_cfg, docker_compose_overwrite_cfg, runtime_cfg
    )
    assert compose_spec.services is not None
    assert isinstance(compose_spec.services, dict)

    service_name = next(iter(compose_spec.services.keys()))
    # pylint: disable=unsubscriptable-object
    assert isinstance(compose_spec.services[service_name], Service)
    build_spec = compose_spec.services[service_name].build
    assert build_spec
    assert isinstance(build_spec, BaseModel)

    print(build_spec.model_dump_json(exclude_unset=True, indent=2))
    print(yaml.safe_dump(compose_spec.model_dump(exclude_unset=True), sort_keys=False))


def test_image_digest_is_not_a_label_annotation(tests_data_dir: Path):
    meta_cfg = MetadataConfig.from_yaml(tests_data_dir / "metadata-dynamic.yml")

    assert meta_cfg.image_digest is None
    meta_cfg.image_digest = hashlib.sha256(b"this is the image manifest").hexdigest()

    annotations = meta_cfg.to_labels_annotations()
    assert not any("digest" in key for key in annotations)
