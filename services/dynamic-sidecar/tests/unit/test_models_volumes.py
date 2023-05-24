# pylint: disable=redefined-outer-name

import pytest
from pytest import FixtureRequest
from simcore_service_dynamic_sidecar.models.volumes import VolumeState, VolumeStatus


@pytest.fixture(params=VolumeStatus)
def status(request: FixtureRequest) -> VolumeStatus:
    return request.param


def test_volume_state_equality(status: VolumeStatus):
    assert VolumeState(status=status) == VolumeState(status=status)
    schema_property_count = len(VolumeState.schema()["properties"])
    assert len(VolumeState(status=status).dict()) == schema_property_count
