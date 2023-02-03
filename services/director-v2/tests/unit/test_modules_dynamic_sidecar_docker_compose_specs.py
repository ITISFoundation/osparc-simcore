# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import json
from typing import Any

import pytest
import yaml
from models_library.service_settings_labels import (
    ComposeSpecLabel,
    SimcoreServiceLabels,
)
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ResourcesDict,
    ServiceResourcesDict,
)
from pydantic import parse_obj_as
from servicelib.resources import CPU_RESOURCE_LIMIT_KEY, MEM_RESOURCE_LIMIT_KEY
from simcore_service_director_v2.modules.dynamic_sidecar import docker_compose_specs


def test_parse_and_export_of_compose_environment_section():
    # sample from https://docs.docker.com/compose/compose-file/compose-file-v3/#environment

    compose_as_dict = yaml.safe_load(
        """
environment:
  RACK_ENV: development
  SHOW: 'true'
  SESSION_SECRET:
    """
    )
    assert isinstance(compose_as_dict["environment"], dict)

    compose_as_list_str = yaml.safe_load(
        """
environment:
  - RACK_ENV=development
  - SHOW=true
  - SESSION_SECRET
    """
    )

    assert isinstance(compose_as_list_str["environment"], list)

    assert docker_compose_specs._environment_section.parse(
        compose_as_dict["environment"]
    ) == docker_compose_specs._environment_section.parse(
        compose_as_list_str["environment"]
    )

    assert (
        docker_compose_specs._environment_section.parse(
            compose_as_list_str["environment"]
        )
        == compose_as_dict["environment"]
    )

    envs = docker_compose_specs._environment_section.export_as_list(
        compose_as_dict["environment"]
    )
    assert envs == compose_as_list_str["environment"]


@pytest.mark.parametrize(
    "service_spec, service_resources",
    [
        pytest.param(
            {"version": "2.3", "services": {DEFAULT_SINGLE_SERVICE_NAME: {}}},
            parse_obj_as(
                ServiceResourcesDict,
                {
                    DEFAULT_SINGLE_SERVICE_NAME: {
                        "image": "simcore/services/dynamic/jupyter-math:2.0.5",
                        "resources": {
                            "CPU": {"limit": 1.1, "reservation": 4.0},
                            "RAM": {"limit": 17179869184, "reservation": 536870912},
                        },
                    },
                },
            ),
            id="compose_spec_2.3",
        ),
        pytest.param(
            {"version": "3.7", "services": {DEFAULT_SINGLE_SERVICE_NAME: {}}},
            parse_obj_as(
                ServiceResourcesDict,
                {
                    DEFAULT_SINGLE_SERVICE_NAME: {
                        "image": "simcore/services/dynamic/jupyter-math:2.0.5",
                        "resources": {
                            "CPU": {"limit": 1.1, "reservation": 4.0},
                            "RAM": {"limit": 17179869184, "reservation": 536870912},
                        },
                    },
                },
            ),
            id="compose_spec_3.7",
        ),
    ],
)
async def test_inject_resource_limits_and_reservations(
    service_spec: dict[str, Any],
    service_resources: ServiceResourcesDict,
) -> None:
    docker_compose_specs._update_resource_limits_and_reservations(
        service_spec=service_spec, service_resources=service_resources
    )

    compose_spec_version_major = int(service_spec["version"].split(".")[0])

    resources: ResourcesDict = service_resources[DEFAULT_SINGLE_SERVICE_NAME].resources
    cpu = resources["CPU"]
    memory = resources["RAM"]

    if compose_spec_version_major >= 3:
        for spec in service_spec["services"].values():
            assert (
                spec["deploy"]["resources"]["reservations"]["cpus"] == cpu.reservation
            )
            assert (
                spec["deploy"]["resources"]["reservations"]["memory"]
                == f"{memory.reservation}"
            )
            assert spec["deploy"]["resources"]["limits"]["cpus"] == cpu.limit
            assert spec["deploy"]["resources"]["limits"]["memory"] == f"{memory.limit}"

            assert (
                f"{CPU_RESOURCE_LIMIT_KEY}={int(cpu.limit*10**9)}"
                in spec["environment"]
            )
            assert f"{MEM_RESOURCE_LIMIT_KEY}={memory.limit}" in spec["environment"]
    else:
        for spec in service_spec["services"].values():
            assert spec["mem_limit"] == f"{memory.limit}"
            assert spec["mem_reservation"] == f"{memory.reservation}"
            assert int(spec["mem_reservation"]) <= int(spec["mem_limit"])
            assert spec["cpus"] == max(cpu.limit, cpu.reservation)

            assert (
                f"{CPU_RESOURCE_LIMIT_KEY}={int(max(cpu.limit, cpu.reservation)*10**9)}"
                in spec["environment"]
            )
            assert f"{MEM_RESOURCE_LIMIT_KEY}={memory.limit}" in spec["environment"]


@pytest.mark.parametrize(
    "compose_spec, storage_opt_count",
    [
        pytest.param(
            json.loads(
                SimcoreServiceLabels.Config.schema_extra["examples"][2][
                    "simcore.service.compose-spec"
                ]
            ),
            2,
            id="two_storage_opt_entries",
        ),
        pytest.param(
            {
                "version": "2.3",
                "services": {
                    "rt-web": {"storage_opt": None},
                    "s4l-core": {},
                },
            },
            1,
            id="one_storage_opt_entry",
        ),
        pytest.param(
            {"version": "2.3", "services": {"rt-web": {}, "s4l-core": {}}},
            0,
            id="no_storage_opt_entry",
        ),
    ],
)
@pytest.mark.parametrize("has_quota_support", [True, False])
def test_update_service_quotas_storage(
    compose_spec: ComposeSpecLabel, storage_opt_count: int, has_quota_support: bool
):
    assert json.dumps(compose_spec).count("storage_opt") == storage_opt_count
    if not has_quota_support:
        docker_compose_specs._strip_service_quotas(service_spec=compose_spec)

    if has_quota_support:
        assert json.dumps(compose_spec).count("storage_opt") == storage_opt_count
    else:
        assert "storage_opt" not in json.dumps(compose_spec)
