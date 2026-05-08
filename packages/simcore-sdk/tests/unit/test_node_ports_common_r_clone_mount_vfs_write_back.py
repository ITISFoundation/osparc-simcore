# pylint: disable=protected-access

import pytest
from settings_library.r_clone import SimcoreSDKMountSettings
from simcore_sdk.node_ports_common.r_clone_utils import (
    _parse_rclone_duration_to_seconds,
    get_effective_vfs_write_back_seconds,
    overwrite_command,
)


@pytest.mark.parametrize(
    "duration_str, expected_seconds",
    [
        pytest.param("30s", 30, id="30s"),
        pytest.param("5s", 5, id="5s"),
        pytest.param("1m", 60, id="1m"),
        pytest.param("1m30s", 90, id="1m30s"),
        pytest.param("2h", 7200, id="2h"),
        pytest.param("1h30m", 5400, id="1h30m"),
        pytest.param("60", 60, id="plain-integer"),
    ],
)
def test_parse_rclone_duration_to_seconds(duration_str: str, expected_seconds: int):
    assert _parse_rclone_duration_to_seconds(duration_str) == expected_seconds


def test_parse_rclone_duration_invalid_returns_zero():
    assert _parse_rclone_duration_to_seconds("invalid") == 0


def _resolve(settings: SimcoreSDKMountSettings) -> list[str]:
    command_parts = ["rclone", "mount", "--vfs-write-back", "30s", "--cache-dir", "/some-folder"]
    return overwrite_command(
        command_parts,
        edit=settings.R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_EDIT_ARGUMENTS,
        remove=settings.R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_REMOVE_ARGUMENTS,
    )


def test_get_effective_vfs_write_back_seconds_default():
    resolved = _resolve(SimcoreSDKMountSettings())
    assert get_effective_vfs_write_back_seconds(resolved) == 30


def test_get_effective_vfs_write_back_seconds_with_edit():
    settings = SimcoreSDKMountSettings(
        R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_EDIT_ARGUMENTS={
            "--vfs-write-back": ("--vfs-write-back", "5s"),
        }
    )
    resolved = _resolve(settings)
    assert get_effective_vfs_write_back_seconds(resolved) == 5


def test_get_effective_vfs_write_back_seconds_with_removal():
    settings = SimcoreSDKMountSettings(
        R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_REMOVE_ARGUMENTS=[
            ("--vfs-write-back", 2),
        ]
    )
    resolved = _resolve(settings)
    assert get_effective_vfs_write_back_seconds(resolved) == 0
