import json
import logging
from typing import Final
from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter
from settings_library.r_clone import EditArguments, RemoveArguments
from simcore_sdk.node_ports_common.r_clone_utils import (
    SyncProgressLogParser,
    _RCloneSyncMessageBase,
    _RCloneSyncMessages,
    _RCloneSyncTransferCompletedMessage,
    _RCloneSyncTransferringMessage,
    _RCloneSyncUpdatedMessage,
    _sanitize_rclone_command,
    get_effective_vfs_write_back_seconds,
    overwrite_command,
)


@pytest.mark.parametrize(
    "log_message,expected",
    [
        (
            '{"level":"info","msg":"There was nothing to transfer","source":"sync/sync.go:954","time":"2024-09-25T10:18:04.904537+00:00"}',  # noqa: E501
            _RCloneSyncMessageBase,
        ),
        (
            '{"level":"info","msg":"","object":".hidden_do_not_remove","objectType":"*s3.Object","source":"operations/operations.go:277","time":"2024-09-24T07:11:22.147117+00:00"}',
            _RCloneSyncUpdatedMessage,
        ),
        (
            '{"level":"info","msg":"Copied (new)","object":"README.ipynb","objectType":"*s3.Object","size":5123,"source":"operations/copy.go:360","time":"2024-04-23T14:05:10.408277+00:00"}',  # noqa: E501
            _RCloneSyncTransferCompletedMessage,
        ),
        (
            json.dumps(
                {
                    "level": "",
                    "msg": "",
                    "source": "",
                    "time": "2024-09-24T07:11:22.147117+00:00",
                    "object": "str",
                }
            ),
            _RCloneSyncUpdatedMessage,
        ),
        (
            json.dumps(
                {
                    "level": "",
                    "msg": "",
                    "source": "",
                    "time": "2024-09-24T07:11:22.147117+00:00",
                    "object": "str",
                    "size": 1,
                }
            ),
            _RCloneSyncTransferCompletedMessage,
        ),
        (
            json.dumps(
                {
                    "level": "",
                    "msg": "",
                    "source": "",
                    "time": "2024-09-24T07:11:22.147117+00:00",
                    "stats": {"bytes": 1, "totalBytes": 1},
                }
            ),
            _RCloneSyncTransferringMessage,
        ),
    ],
)
async def test_rclone_stbc_message_parsing_regression(log_message: str, expected: type):
    parsed_log = TypeAdapter(_RCloneSyncMessages).validate_json(log_message)
    assert isinstance(parsed_log, expected)

    progress_log_parser = SyncProgressLogParser(AsyncMock())
    await progress_log_parser(log_message)


_SOURCE_COMMAND: Final[list[str]] = [
    "rclone",
    "--config",
    "/path/to/config",
    "--transfers",
    "16",
    "--buffer-size",
    "0M",
    "sync",
    "source:path",
    "destination:path",
]


@pytest.mark.parametrize(
    "edit,remove,expected_command",
    [
        pytest.param(
            TypeAdapter(EditArguments).validate_python({}),
            TypeAdapter(RemoveArguments).validate_python([]),
            _SOURCE_COMMAND,
            id="no-changes",
        ),
        pytest.param(
            TypeAdapter(EditArguments).validate_python(
                {
                    "--transfers": ["--transfers", "32"],
                    "--buffer-size": ("--buffer-size-X", "16M"),
                    "sync": "copy",
                    "--vv": "-vv",
                    "-add": ("-add", "3"),
                }
            ),
            TypeAdapter(RemoveArguments).validate_python([("--config", 2)]),
            [
                "rclone",
                "--transfers",
                "32",
                "--buffer-size-X",
                "16M",
                "copy",
                "source:path",
                "destination:path",
                "-vv",
                "-add",
                "3",
            ],
            id="edit-existing-edit-adding-remove",
        ),
        pytest.param(
            TypeAdapter(EditArguments).validate_python({}),
            TypeAdapter(RemoveArguments).validate_python([("--config", 4)]),
            [
                "rclone",
                "--buffer-size",
                "0M",
                "sync",
                "source:path",
                "destination:path",
            ],
            id="remove-a-lot-in-a-row",
        ),
        pytest.param(
            TypeAdapter(EditArguments).validate_python({}),
            TypeAdapter(RemoveArguments).validate_python([["--config", 2], ["--transfers", 2]]),
            [
                "rclone",
                "--buffer-size",
                "0M",
                "sync",
                "source:path",
                "destination:path",
            ],
            id="regression-remove-consecutive-arguments",
        ),
    ],
)
def test_overwrite_command(edit: EditArguments, remove: RemoveArguments, expected_command: list[str]) -> None:
    assert overwrite_command(_SOURCE_COMMAND, edit=edit, remove=remove) == expected_command


@pytest.mark.parametrize(
    "command,expected_sanitized",
    [
        pytest.param(
            [
                "rclone",
                "--config",
                "/path/to/config",
                "--transfers",
                "16",
            ],
            [
                "rclone",
                "--config",
                "/path/to/config",
                "--transfers",
                "16",
            ],
            id="no-sensitive-data",
        ),
        pytest.param(
            [
                "rclone",
                "--pass",
                "my-secret-password",
                "sync",
                "source",
                "dest",
            ],
            [
                "rclone",
                "--pass",
                "********",
                "sync",
                "source",
                "dest",
            ],
            id="mask-pass-flag",
        ),
        pytest.param(
            [
                "rclone",
                "--password=my-secret-password",
                "sync",
            ],
            [
                "rclone",
                "--password=********",
                "sync",
            ],
            id="mask-password-embedded",
        ),
        pytest.param(
            [
                "rclone",
                "--secret-access-key",
                "AKIA1234567890ABCDEF",
                "--access-key-id",
                "AKIAIOSFODNN7EXAMPLE",
            ],
            [
                "rclone",
                "--secret-access-key",
                "********",
                "--access-key-id",
                "********",
            ],
            id="mask-aws-credentials",
        ),
        pytest.param(
            [
                "rclone",
                "--api-key",
                "sk_test_123456789",
                "--bearer-token=some_token_value",
            ],
            [
                "rclone",
                "--api-key",
                "********",
                "--bearer-token=********",
            ],
            id="mask-api-keys",
        ),
        pytest.param(
            [
                "rclone",
                "--auth",
                "user:password",
                "--client-secret",
                "client_secret_value",
                "--config",
                "/etc/rclone.conf",
            ],
            [
                "rclone",
                "--auth",
                "********",
                "--client-secret",
                "********",
                "--config",
                "/etc/rclone.conf",
            ],
            id="mask-auth-and-client-secret",
        ),
        pytest.param(
            [
                "rclone",
                "--client-id=my_id",
                "--pass=secret",
                "sync",
            ],
            [
                "rclone",
                "--client-id=********",
                "--pass=********",
                "sync",
            ],
            id="mask-multiple-embedded-flags",
        ),
        pytest.param(
            [
                "rclone",
                "mount",
                "--rc-user='11111111-2222-3333-4444-555555555555'",
                "--rc-pass='66666666-7777-8888-9999-000000000000'",
                "--rc-addr=0.0.0.0:5572",
                "remote:bucket",
                "/mnt/data",
            ],
            [
                "rclone",
                "mount",
                "--rc-user=********",
                "--rc-pass=********",
                "--rc-addr=0.0.0.0:5572",
                "remote:bucket",
                "/mnt/data",
            ],
            id="mask-rc-credentials",
        ),
        pytest.param(
            [
                "rclone",
                "mount",
                "--access-key-id",
                "AKIAIOSFODNN7EXAMPLE",
                "--secret-access-key",
                "wJalrXUtnFEMI1234567890",
                "--rc-user='uuid-user'",
                "--rc-pass='uuid-pass'",
                "--vfs-write-back",
                "30s",
            ],
            [
                "rclone",
                "mount",
                "--access-key-id",
                "********",
                "--secret-access-key",
                "********",
                "--rc-user=********",
                "--rc-pass=********",
                "--vfs-write-back",
                "30s",
            ],
            id="mask-storage-and-rc-credentials-together",
        ),
        pytest.param(
            [
                "rclone",
                "sync",
                "--s3-access-key-id",
                "AKIAIOSFODNN7EXAMPLE",
                "--s3-secret-access-key=wJalrXUtnFEMI",
                "src:",
                "dst",
            ],
            [
                "rclone",
                "sync",
                "--s3-access-key-id",
                "********",
                "--s3-secret-access-key=********",
                "src:",
                "dst",
            ],
            id="mask-backend-prefixed-credentials",
        ),
        pytest.param(
            [
                "rclone",
                "--pass",
                "-dash-prefixed-password",
            ],
            [
                "rclone",
                "--pass",
                "********",
            ],
            id="mask-dash-prefixed-value",
        ),
    ],
)
def test_sanitize_rclone_command(command: list[str], expected_sanitized: list[str]):
    """Test that sensitive data in rclone commands is properly masked."""
    assert _sanitize_rclone_command(command) == expected_sanitized


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(
            ["rclone", "--rc-user='user-uuid'", "--rc-pass='pass-uuid'", "mount"],
            id="flag-not-found",
        ),
        pytest.param(
            ["rclone", "--rc-user='user-uuid'", "--rc-pass='pass-uuid'", "--vfs-write-back"],
            id="flag-missing-value",
        ),
    ],
)
def test_get_effective_vfs_write_back_seconds_error_messages_do_not_leak_credentials(command: list[str]):
    with pytest.raises(ValueError, match="--vfs-write-back") as exc_info:
        get_effective_vfs_write_back_seconds(command)
    assert "user-uuid" not in str(exc_info.value)
    assert "pass-uuid" not in str(exc_info.value)


def test_overwrite_command_warning_log_does_not_leak_credentials(caplog: pytest.LogCaptureFixture):
    command = ["rclone", "--rc-pass='pass-uuid'", "sync", "src:", "dst"]
    with caplog.at_level(logging.WARNING):
        overwrite_command(command, edit={}, remove=[("--transfers", 1)])
    assert "--transfers" in caplog.text
    assert "pass-uuid" not in caplog.text
