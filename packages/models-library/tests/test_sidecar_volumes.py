# pylint: disable=redefined-outer-name

import pytest
from models_library.sidecar_volumes import VolumeState, VolumeStatus
from pytest import FixtureRequest


@pytest.fixture(params=VolumeStatus)
def status(request: FixtureRequest) -> VolumeStatus:
    return request.param


def test_volume_state_equality_does_not_use_last_changed(status: VolumeStatus):
    # NOTE: `last_changed` is initialized with the utc datetime
    #  at the moment of the creation of the object.
    assert VolumeState(status=status) == VolumeState(status=status)
    schema_property_count = len(VolumeState.schema()["properties"])
    assert len(VolumeState(status=status).dict()) == schema_property_count
