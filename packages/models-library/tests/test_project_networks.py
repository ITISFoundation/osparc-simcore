# pylint: disable=redefined-outer-name
import json
from typing import Dict
from uuid import UUID, uuid4

import pytest
from models_library.project_networks import (
    DockerNetworkAlias,
    DockerNetworkName,
    NetworksWithAliases,
    ProjectNetworks,
)
from pydantic import ValidationError, parse_obj_as

# UTILS


# FIXTURES


@pytest.fixture
def uuid() -> UUID:
    return uuid4()


# TESTS


@pytest.mark.parametrize("example", NetworksWithAliases.Config.schema_extra["examples"])
def test_networks_with_aliases(example: Dict) -> None:
    project_networks = NetworksWithAliases.parse_obj(example)
    assert json.loads(project_networks.json()) == example
    assert project_networks.json() == json.dumps(example)


@pytest.mark.parametrize(
    "invalid_example",
    [
        {"1_NO_START_WITH_NUMBER": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
        {"_NO_UNDERSCORE_START": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
        {"-NO_DASH_START": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
        {
            "MAX_64_CHARS_ALLOWED_DUE_TO_DOCKER_NETWORK_LIMITATIONS___________": {
                "5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"
            }
        },
        {"i_am_ok": {"NOT_A_VALID_UUID": "ok"}},
        {"i_am_ok": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "1_I_AM_INVALID"}},
    ],
)
def test_networks_with_aliases_fail(invalid_example: Dict) -> None:
    with pytest.raises(ValidationError):
        assert NetworksWithAliases.parse_obj(invalid_example)


@pytest.mark.parametrize("network_name", ["a", "ok", "a_", "A_", "a1", "a-"])
def test_project_networks_validation(network_name: str) -> None:
    assert parse_obj_as(DockerNetworkName, network_name) == network_name
    assert parse_obj_as(DockerNetworkAlias, network_name) == network_name


@pytest.mark.parametrize("network_name", ["", "1", "-", "_"])
def test_project_networks_validation_fails(network_name: str) -> None:
    with pytest.raises(ValidationError):
        parse_obj_as(DockerNetworkName, network_name)
    with pytest.raises(ValidationError):
        parse_obj_as(DockerNetworkAlias, network_name)


def test_project_networks() -> None:
    assert ProjectNetworks.parse_obj(ProjectNetworks.Config.schema_extra["example"])


def test_class_constructors_fail() -> None:
    with pytest.raises(ValidationError):
        NetworksWithAliases.parse_obj(
            {
                "ok-netowrk_naeme": {
                    UUID(
                        "5057e2c1-d392-4d31-b5c8-19f3db780390"
                    ): "not_allowed with_ uuid"
                }
            }
        )
