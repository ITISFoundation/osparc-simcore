from models_library.sharing_networks import SharingNetworks
from pydantic import ValidationError
import pytest
from typing import Dict


@pytest.mark.parametrize("example", SharingNetworks.Config.schema_extra["examples"][:2])
def test_sharing_networks(example: Dict) -> None:
    assert SharingNetworks.parse_obj(example)


@pytest.mark.parametrize("example", SharingNetworks.Config.schema_extra["examples"][2:])
def test_sharing_networks_fail(example: Dict) -> None:
    with pytest.raises(ValidationError):
        assert SharingNetworks.parse_obj(example)
