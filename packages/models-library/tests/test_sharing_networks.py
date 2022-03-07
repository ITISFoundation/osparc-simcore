# pylint: disable=redefined-outer-name
import json
from typing import Any, Dict
from uuid import UUID

import pytest
from models_library.sharing_networks import (
    NetworksWithAliases,
    SharingNetworks,
    validate_network_alias,
    validate_network_name,
)
from pydantic import ValidationError

# UTILS


def _keys_as_uuid(data: Dict[str, Any]) -> Dict[UUID, Any]:
    return {UUID(k): v for k, v in data.items()}


def _keys_as_str(data: Dict[str, Any]) -> Dict[str, Any]:
    return {f"{k}": v for k, v in data.items()}


# FIXTURES


@pytest.fixture(params=[True, False])
def cast_to_uuid(request) -> bool:
    return request.param


# TESTS


@pytest.mark.parametrize("example", NetworksWithAliases.Config.schema_extra["examples"])
def test_networks_with_aliases(example: Dict, cast_to_uuid: bool) -> None:
    if cast_to_uuid:
        example = {k: _keys_as_uuid(v) for k, v in example.items()}

    expected_example = {k: _keys_as_str(v) for k, v in example.items()}
    sharing_networks = NetworksWithAliases.parse_obj(example)
    assert sharing_networks.dict() == expected_example
    assert sharing_networks.json() == json.dumps(expected_example)


@pytest.mark.parametrize(
    "example", NetworksWithAliases.Config.schema_extra["invalid_examples"]
)
def test_networks_with_aliases_fail(example: Dict) -> None:
    with pytest.raises(ValidationError):
        assert NetworksWithAliases.parse_obj(example)


@pytest.mark.parametrize("network_name", ["a", "ok", "a_", "A_", "a1", "a-"])
def test_service_network_validation(network_name: str) -> None:
    assert validate_network_name(network_name)
    assert validate_network_alias(network_name)


@pytest.mark.parametrize("network_name", ["", "1", "-", "_"])
def test_service_network_validation_fails(network_name: str) -> None:
    with pytest.raises(ValidationError):
        assert validate_network_name(network_name)
    with pytest.raises(ValidationError):
        assert validate_network_alias(network_name)


def test_sharing_networks() -> None:
    assert SharingNetworks.parse_obj(SharingNetworks.Config.schema_extra["example"])
