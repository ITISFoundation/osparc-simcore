from typing import Dict

import pytest
from models_library.sharing_networks import (
    SharingNetworks,
    validate_network_name,
    validate_network_alias,
)
from pydantic import Field, ValidationError


@pytest.mark.parametrize("example", SharingNetworks.Config.schema_extra["examples"])
def test_sharing_networks(example: Dict) -> None:
    assert SharingNetworks.parse_obj(example)


@pytest.mark.parametrize(
    "example", SharingNetworks.Config.schema_extra["invalid_examples"]
)
def test_sharing_networks_fail(example: Dict) -> None:
    with pytest.raises(ValidationError):
        assert SharingNetworks.parse_obj(example)


@pytest.mark.parametrize("network_name", ["a", "ok", "a_", "A_", "a1", "a-"])
def test_servoce_network_validation(network_name: str) -> None:
    assert validate_network_name(network_name)
    assert validate_network_alias(network_name)


@pytest.mark.parametrize("network_name", ["", "1", "-", "_"])
def test_servoce_network_validation_fails(network_name: str) -> None:
    with pytest.raises(ValidationError):
        assert validate_network_name(network_name)
    with pytest.raises(ValidationError):
        assert validate_network_alias(network_name)
