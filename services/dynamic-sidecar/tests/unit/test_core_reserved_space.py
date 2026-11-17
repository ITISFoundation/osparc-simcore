# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# ruff: noqa: SLF001


from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_dynamic_sidecar.core import reserved_space
from simcore_service_dynamic_sidecar.core.application import create_base_app


def test_reserved_disk_space_workflow(cleanup_reserved_disk_space: None, mock_environment: EnvVarsDict):
    assert not reserved_space._RESERVED_DISK_SPACE_NAME.exists()
    create_base_app()

    assert reserved_space._RESERVED_DISK_SPACE_NAME.exists()
    assert reserved_space._RESERVED_DISK_SPACE_NAME.stat().st_size == TypeAdapter(ByteSize).validate_python("10MiB")

    reserved_space.free_reserved_disk_space()
    assert not reserved_space._RESERVED_DISK_SPACE_NAME.exists()
