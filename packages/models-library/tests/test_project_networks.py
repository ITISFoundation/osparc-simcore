# pylint: disable=redefined-outer-name
from uuid import UUID

import pytest
from models_library.projects_networks import (
    DockerNetworkAlias,
    DockerNetworkName,
    NetworksWithAliases,
)
from pydantic import TypeAdapter, ValidationError


@pytest.mark.parametrize(
    "valid_example",
    [
        {"nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
        {"C": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
        {"shr-ntwrk_5c743ad2-8fdb-11ec-bb3a-02420a000008_default": {}},
    ],
)
def test_networks_with_aliases_ok(valid_example: dict) -> None:
    assert NetworksWithAliases.model_validate(valid_example)


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
def test_networks_with_aliases_fail(invalid_example: dict) -> None:
    with pytest.raises(ValidationError):
        assert NetworksWithAliases.model_validate(invalid_example)


@pytest.mark.parametrize("network_name", ["a", "ok", "a_", "A_", "a1", "a-"])
def test_projects_networks_validation(network_name: str) -> None:
    assert TypeAdapter(DockerNetworkName).validate_python(network_name) == network_name
    assert TypeAdapter(DockerNetworkAlias).validate_python(network_name) == network_name


@pytest.mark.parametrize("network_name", ["", "1", "-", "_"])
def test_projects_networks_validation_fails(network_name: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(DockerNetworkName).validate_python(network_name)
    with pytest.raises(ValidationError):
        TypeAdapter(DockerNetworkAlias).validate_python(network_name)


def test_class_constructors_fail() -> None:
    with pytest.raises(ValidationError):
        NetworksWithAliases.model_validate(
            {
                "ok-netowrk_naeme": {
                    UUID(
                        "5057e2c1-d392-4d31-b5c8-19f3db780390"
                    ): "not_allowed with_ uuid"
                }
            }
        )
