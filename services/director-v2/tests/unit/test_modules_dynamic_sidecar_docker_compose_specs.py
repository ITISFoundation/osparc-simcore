# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import json
from dataclasses import dataclass
from importlib import reload
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock

import pytest
import yaml
from models_library.service_settings_labels import SimcoreServiceLabels
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.modules.dynamic_sidecar import docker_compose_specs

# UTILS


@dataclass
class Expect:
    limit_memory_bytes: int
    limit_nano_cpus: int
    reservation_memory_bytes: int
    reservation_nano_cpus: int


# FIXTURES


@pytest.fixture
def mock_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_get_labels_for_involved_services(mocker: MockerFixture) -> None:
    def _mocked_get_labels_for_involved_services(
        *args, **kwargs
    ) -> Dict[str, SimcoreServiceLabels]:
        return {
            "all_defined": SimcoreServiceLabels.parse_obj(
                {
                    "simcore.service.settings": json.dumps(
                        [
                            {
                                "name": "Resources",
                                "type": "Resources",
                                "value": {
                                    "Limits": {
                                        "NanoCPUs": 4000000000,
                                        "MemoryBytes": 17179869184,
                                    },
                                    "Reservations": {
                                        "NanoCPUs": 110000000,
                                        "MemoryBytes": 536870912,
                                    },
                                },
                            },
                        ]
                    )
                }
            ),
            "all_missing": SimcoreServiceLabels.parse_obj(
                {"simcore.service.settings": json.dumps([])}
            ),
            "only_limits": SimcoreServiceLabels.parse_obj(
                {
                    "simcore.service.settings": json.dumps(
                        [
                            {
                                "name": "Resources",
                                "type": "Resources",
                                "value": {
                                    "Limits": {
                                        "NanoCPUs": 4000000000,
                                        "MemoryBytes": 17179869184,
                                    },
                                },
                            },
                        ]
                    )
                }
            ),
            "only_reservations": SimcoreServiceLabels.parse_obj(
                {
                    "simcore.service.settings": json.dumps(
                        [
                            {
                                "name": "Resources",
                                "type": "Resources",
                                "value": {
                                    "Reservations": {
                                        "NanoCPUs": 110000000,
                                        "MemoryBytes": 536870912,
                                    },
                                },
                            },
                        ]
                    )
                }
            ),
        }

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.settings.get_labels_for_involved_services",
        side_effect=_mocked_get_labels_for_involved_services,
    )

    reload(docker_compose_specs)


@pytest.fixture
def service_key() -> str:
    return "simcore/services/dynamic/test_image"


@pytest.fixture
def service_tag() -> str:
    return "1.0.0"


@pytest.fixture
def compose_spec() -> Dict[str, Any]:
    return {}


# TESTS


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


EXPECT_ALL_DEFINED = Expect(
    limit_memory_bytes=17179869184,
    limit_nano_cpus=4000000000,
    reservation_memory_bytes=536870912,
    reservation_nano_cpus=110000000,
)
EXPECT_ALL_MISSING = Expect(
    limit_memory_bytes=docker_compose_specs.DEFAULT_LIMIT_MEMORY_BYTES,
    limit_nano_cpus=docker_compose_specs.DEFAULT_LIMIT_NANO_CPUS,
    reservation_memory_bytes=docker_compose_specs.DEFAULT_RESERVATION_MEMORY_BYTES,
    reservation_nano_cpus=docker_compose_specs.DEFAULT_RESERVATION_NANO_CPUS,
)

EXPECT_ONLY_LIMITS = Expect(
    limit_memory_bytes=17179869184,
    limit_nano_cpus=4000000000,
    reservation_memory_bytes=docker_compose_specs.DEFAULT_RESERVATION_MEMORY_BYTES,
    reservation_nano_cpus=docker_compose_specs.DEFAULT_RESERVATION_NANO_CPUS,
)
EXPECT_ONLY_RESERVATIONS = Expect(
    # NOTE: limits are raised to match reservations even when not specified
    limit_memory_bytes=536870912,
    limit_nano_cpus=110000000,
    reservation_memory_bytes=536870912,
    reservation_nano_cpus=110000000,
)

TEST_SERVICE_SPECS: List[Tuple[Dict[str, Any], Expect]] = [
    ({"version": "2.3", "services": {"all_defined": {}}}, EXPECT_ALL_DEFINED),
    ({"version": "3", "services": {"all_defined": {}}}, EXPECT_ALL_DEFINED),
    ({"version": "3", "services": {"all_missing": {}}}, EXPECT_ALL_MISSING),
    ({"version": "2", "services": {"all_missing": {}}}, EXPECT_ALL_MISSING),
    ({"version": "3", "services": {"only_limits": {}}}, EXPECT_ONLY_LIMITS),
    ({"version": "2", "services": {"only_limits": {}}}, EXPECT_ONLY_LIMITS),
    ({"version": "3", "services": {"only_reservations": {}}}, EXPECT_ONLY_RESERVATIONS),
    ({"version": "2", "services": {"only_reservations": {}}}, EXPECT_ONLY_RESERVATIONS),
]


@pytest.mark.parametrize("service_spec, expect", TEST_SERVICE_SPECS)
async def test_inject_resource_limits_and_reservations(
    mock_get_labels_for_involved_services: None,
    mock_app: AsyncMock,
    service_key: str,
    service_tag: str,
    service_spec: Dict[str, Any],
    expect: Expect,
) -> None:
    await docker_compose_specs._inject_resource_limits_and_reservations(
        app=mock_app,
        service_key=service_key,
        service_tag=service_tag,
        service_spec=service_spec,
    )

    compose_spec_version_major = int(service_spec["version"].split(".")[0])

    if compose_spec_version_major >= 3:
        for spec in service_spec["services"].values():
            assert (
                spec["deploy"]["resources"]["reservations"]["cpus"]
                == expect.reservation_nano_cpus / docker_compose_specs._NANO_UNIT
            )
            assert (
                spec["deploy"]["resources"]["reservations"]["memory"]
                == f"{expect.reservation_memory_bytes}b"
            )
            assert (
                spec["deploy"]["resources"]["limits"]["cpus"]
                == expect.limit_nano_cpus / docker_compose_specs._NANO_UNIT
            )
            assert (
                spec["deploy"]["resources"]["limits"]["memory"]
                == f"{expect.limit_memory_bytes}b"
            )
    else:
        for spec in service_spec["services"].values():
            assert spec["mem_limit"] == expect.limit_memory_bytes
            assert spec["mem_reservation"] == expect.reservation_memory_bytes
            assert spec["mem_reservation"] <= spec["mem_limit"]
            assert (
                spec["cpus"]
                == max(expect.limit_nano_cpus, expect.reservation_nano_cpus)
                / docker_compose_specs._NANO_UNIT
            )
