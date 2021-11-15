# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import yaml
from pydantic import BaseModel
from service_integration.compose_spec_model import BuildItem
from service_integration.osparc_config import IoOsparcConfig, ServiceOsparcConfig
from service_integration.osparc_image_specs import create_image_spec


def test_create_image_spec_impl(tests_data_dir: Path):
    # have image spec  -> assemble build part of the compose-spec -> ready to build with `docker-compose build`
    # image-spec for devel, prod, ...

    # load & parse osparc configs
    io_spec = IoOsparcConfig.from_yaml(tests_data_dir / "metadata-dynamic.yml")
    service_spec = ServiceOsparcConfig.from_yaml(tests_data_dir / "runtime.yml")

    # assemble docker-compose
    build_spec = BuildItem(
        context=".",
        dockerfile="Dockerfile",
        labels={
            **io_spec.to_labels_annotations(),
            **service_spec.to_labels_annotations(),
        },
    )

    compose_spec = create_image_spec(io_spec, service_spec)
    assert compose_spec.services

    service_name = next(iter(compose_spec.services.keys()))
    build_spec = compose_spec.services[service_name].build
    assert build_spec
    assert isinstance(build_spec, BaseModel)

    print(build_spec.json(exclude_unset=True, indent=2))
    print(yaml.safe_dump(compose_spec.dict(exclude_unset=True), sort_keys=False))
