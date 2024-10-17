# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_dynamic_sidecar.core.application import create_base_app
from simcore_service_dynamic_sidecar.core.reserved_space import (
    _RESERVED_DISK_SPACE_NAME,
    remove_reserved_disk_space,
)


def test_reserved_disk_space_workflow(
    cleanup_reserved_disk_space: None, mock_environment: EnvVarsDict
):
    assert not _RESERVED_DISK_SPACE_NAME.exists()
    create_base_app()

    assert _RESERVED_DISK_SPACE_NAME.exists()
    assert _RESERVED_DISK_SPACE_NAME.stat().st_size == TypeAdapter(
        ByteSize
    ).validate_python("10MiB")

    remove_reserved_disk_space()
    assert not _RESERVED_DISK_SPACE_NAME.exists()
