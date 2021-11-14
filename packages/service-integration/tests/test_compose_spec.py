import random
from pathlib import Path
from typing import Dict, Optional, Type
from uuid import uuid4

import yaml
from pydantic import BaseModel
from service_integration.compose_spec_model import (
    BuildItem,
    ComposeSpecification,
    Service,
    Volume1,
)
from service_integration.osparc_config import (
    IOSpecification,
    PathsMapping,
    ServiceSpecification,
    SettingsItem,
)
from service_integration.osparc_image_specs import create_image_spec
from service_integration.yaml_utils import yaml_safe_load
from simcore_service_director_v2.models.schemas.dynamic_services import service


def auto_map_to_service(settings: Dict):
    def find_field_path(
        field_name, type_name, model_cls: Type[BaseModel], path=""
    ) -> Optional[str]:
        for name, model_field in model_cls.__fields__.items():
            if (
                model_field.name == field_name
                and model_field.type_.__name__ == type_name
            ):
                return f"{path}.{field_name}"
            elif issubclass(model_field.type_, BaseModel):
                return find_field_path(
                    field_name, type_name, model_field.type_, f"{path}.{name}"
                )

    data = {}
    for obj in settings:
        item = SettingsItem.parse_obj(obj)

        parts = []
        if path := find_field_path(item.name, item.type_, Service):
            parts = path.lstrip().split(".")
            dikt = {}
            for key in parts[:-1]:
                dikt = {key: dikt}
            dikt[parts[-1]] = item.value

            data.update(*dikt)

    return Service.parse_obj(data)


def test_create_compose_spec_build(tests_data_dir: Path):

    # load & parse osparc configs
    io_spec = IOSpecification.from_yaml(tests_data_dir / "metadata-dynamic.yml")
    service_spec = ServiceSpecification.from_yaml(tests_data_dir / "service.yml")

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

    build_spec = compose_spec.services[io_spec.image_name()].build
    assert isinstance(build_spec, BaseModel)

    print(build_spec.json(exclude_unset=True, indent=2))

    print(yaml.safe_dump(compose_spec.dict(exclude_unset=True), sort_keys=False))


def test_compose_spec_run(tests_data_dir: Path):

    # have image spec  -> assemble build part of the compose-spec -> ready to build with `docker-compose build`
    # image-spec for devel, prod, ...

    # have spec on how to run -> assemble mounts, network etc of the compose -> ready to run with `docker-compose up`
    # run-spec for devel, prod, etc ...

    osparc_spec: Dict = yaml.safe_load((tests_data_dir / "service.yml").read_text())

    pm_spec1 = PathsMapping.parse_obj(osparc_spec["paths-mapping"])
    pm_spec2 = PathsMapping.parse_obj(
        {
            "outputs_path": "/outputs",
            "inputs_path": "/inputs",
            "state_paths": ["/workdir1", "/workdir2"],
        }
    )

    pm_spec = random.choice([pm_spec1, pm_spec2])

    # A develop mode --

    pid = Path(f"{uuid4()}")
    nid = f"{uuid4()}"

    volumes = [
        Volume1(
            type="bind",
            source=f"{pid / nid / 'inputs'}",
            target=f"{pm_spec.inputs_path}",
            read_only=True,
        ),
        Volume1(
            type="bind",
            source=f"{pid / nid / 'outputs'}",
            target=f"{pm_spec.outputs_path}",
        ),
    ]

    volumes += [
        Volume1(
            type="bind",
            source=f"{pid / nid /'state'/ workdir.name}",
            target=f"{workdir}",
        )
        for workdir in pm_spec.state_paths
    ]

    # FIXME: ensure all sources are different! (e.g. a/b/c  and z/c have the same name!)

    print(Service(volumes=volumes).json(exclude_unset=True, indent=2))

    # TODO: auto_map_to_service(osparc_spec["settings"])
    data = {}
    for obj in osparc_spec["settings"]:
        item = SettingsItem.parse_obj(obj)

        if item.name == "resources":
            # https://docs.docker.com/compose/compose-file/compose-file-v3/#resources
            data["deploy"] = {
                "resources": {
                    "limits": {
                        "cpu": item.value["mem_limit"],
                        "memory": item.value["cpu_limit"],
                    }
                }
            }
        elif item.name == "ports":
            # https://docs.docker.com/compose/compose-file/compose-file-v3/#ports
            data["ports"] = [
                item.value,
            ]
        elif item.name == "constraints":
            # "https://docs.docker.com/compose/compose-file/compose-file-v3/#placement"
            data["deploy"] = {"placement": {"constraints": item.value}}

        else:
            assert False, item

    print(Service(**data).json(exclude_unset=True, indent=2))


def test_compatibility():
    pass


def test_upgrade():
    pass
