# pylint: disable=redefined-outer-name
# pylint: disable=protected-access


from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
import yaml
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ResourcesDict,
    ServiceResourcesDict,
)
from models_library.users import UserID
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


def test_regression_service_has_no_reservations():
    service_spec: dict[str, Any] = {
        "version": "3.7",
        "services": {DEFAULT_SINGLE_SERVICE_NAME: {}},
    }
    service_resources: ServiceResourcesDict = parse_obj_as(ServiceResourcesDict, {})

    spec_before = deepcopy(service_spec)
    docker_compose_specs._update_resource_limits_and_reservations(
        service_spec=service_spec, service_resources=service_resources
    )
    assert spec_before == service_spec


USER_ID: UserID = 1
PROJECT_ID: ProjectID = uuid4()
NODE_ID: NodeID = uuid4()
SIMCORE_USER_AGENT: str = "a-puppet"
PRODUCT_NAME: str = "osparc"


@pytest.mark.parametrize(
    "service_spec, expected_result",
    [
        pytest.param(
            {"services": {"service-1": {}}},
            {
                "services": {
                    "service-1": {
                        "labels": [
                            f"user_id={USER_ID}",
                            f"study_id={PROJECT_ID}",
                            f"uuid={NODE_ID}",
                        ]
                    }
                }
            },
            id="single_service",
        ),
        pytest.param(
            {"services": {"service-1": {}, "service-2": {}}},
            {
                "services": {
                    "service-1": {
                        "labels": [
                            f"user_id={USER_ID}",
                            f"study_id={PROJECT_ID}",
                            f"uuid={NODE_ID}",
                        ]
                    },
                    "service-2": {
                        "labels": [
                            f"user_id={USER_ID}",
                            f"study_id={PROJECT_ID}",
                            f"uuid={NODE_ID}",
                            f"user_agent={SIMCORE_USER_AGENT}",
                            f"product_name={PRODUCT_NAME}",
                        ]
                    },
                }
            },
            id="multiple_services",
        ),
    ],
)
async def test_update_container_labels(
    service_spec: dict[str, Any], expected_result: dict[str, Any]
):
    docker_compose_specs._update_container_labels(
        service_spec, USER_ID, PROJECT_ID, NODE_ID, SIMCORE_USER_AGENT, PRODUCT_NAME
    )
    assert service_spec == expected_result
