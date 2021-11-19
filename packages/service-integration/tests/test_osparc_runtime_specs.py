# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import random
from pathlib import Path
from typing import Dict
from uuid import uuid4

import yaml
from service_integration.compose_spec_model import Service, ServiceVolume
from service_integration.osparc_config import PathsMapping, SettingsItem


def test_create_runtime_spec_impl(tests_data_dir: Path):

    # have spec on how to run -> assemble mounts, network etc of the compose -> ready to run with `docker-compose up`
    # run-spec for devel, prod, etc ...

    osparc_spec: Dict = yaml.safe_load((tests_data_dir / "runtime.yml").read_text())

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
        ServiceVolume(
            type="bind",
            source=f"{pid / nid / 'inputs'}",
            target=f"{pm_spec.inputs_path}",
            read_only=True,
        ),
        ServiceVolume(
            type="bind",
            source=f"{pid / nid / 'outputs'}",
            target=f"{pm_spec.outputs_path}",
        ),
    ]

    volumes += [
        ServiceVolume(
            type="bind",
            source=f"{pid / nid /'state'/ workdir.name}",
            target=f"{workdir}",
        )
        for workdir in pm_spec.state_paths
    ]

    # FIXME: ensure all sources are different! (e.g. a/b/c  and z/c have the same name!)

    print(Service(volumes=volumes).json(exclude_unset=True, indent=2))

    # TODO: _auto_map_to_service(osparc_spec["settings"])
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
