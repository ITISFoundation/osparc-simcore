import json
from typing import Any, Dict

import pytest
from models_library.sharing_networks import (
    SharingNetworks,
    validate_network_alias,
    validate_network_name,
)
from pydantic import ValidationError


@pytest.mark.parametrize("example", SharingNetworks.Config.schema_extra["examples"])
def test_sharing_networks(example: Dict) -> None:
    def _keys_as_str(data: Dict[str, Any]) -> Dict[str, Any]:
        return {f"{k}": v for k, v in data.items()}

    expected_example = {k: _keys_as_str(v) for k, v in example.items()}
    sharing_networks = SharingNetworks.parse_obj(example)
    assert sharing_networks.dict() == expected_example
    assert sharing_networks.json() == json.dumps(expected_example)


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
