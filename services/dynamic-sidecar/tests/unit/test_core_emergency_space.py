# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_dynamic_sidecar.core.application import create_base_app
from simcore_service_dynamic_sidecar.core.emergency_space import (
    _EMERGENCY_DISK_SPACE_NAME,
    remove_emergency_disk_space,
)


def test_emergency_disk_space_workflow(
    cleanup_emergency_disk_space: None, mock_environment: EnvVarsDict
):
    assert not _EMERGENCY_DISK_SPACE_NAME.exists()
    create_base_app()

    assert _EMERGENCY_DISK_SPACE_NAME.exists()
    assert _EMERGENCY_DISK_SPACE_NAME.stat().st_size == parse_obj_as(ByteSize, "10MiB")

    remove_emergency_disk_space()
    assert not _EMERGENCY_DISK_SPACE_NAME.exists()
