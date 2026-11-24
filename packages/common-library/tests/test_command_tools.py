from typing import Final

import pytest
from common_library.command_tools import sanitize_command

_PLACEHOLDER: Final[str] = "*" * 8
_SENSITIVE_FLAGS: Final[frozenset[str]] = frozenset({"--token", "--secret"})


@pytest.mark.parametrize(
    "command,expected",
    [
        pytest.param([], [], id="empty"),
        pytest.param(["copy", "src", "dst"], ["copy", "src", "dst"], id="no-flags"),
        pytest.param(
            ["rclone", "--verbose", "sync", "a", "b"],
            ["rclone", "--verbose", "sync", "a", "b"],
            id="non-sensitive-flags-passthrough",
        ),
        pytest.param(
            ["rclone", "--token", "abc"],
            ["rclone", "--token", _PLACEHOLDER],
            id="space-separated-value-masked",
        ),
        pytest.param(
            ["rclone", "--token=abc"],
            ["rclone", f"--token={_PLACEHOLDER}"],
            id="equals-form-value-masked",
        ),
        pytest.param(
            ["rclone", "--name=Bob"],
            ["rclone", "--name=Bob"],
            id="equals-form-non-sensitive-passthrough",
        ),
        pytest.param(
            ["--token", "-hidden"],
            ["--token", _PLACEHOLDER],
            id="value-starting-with-dash-still-masked",
        ),
        pytest.param(["--token"], ["--token"], id="trailing-flag-without-value"),
        pytest.param(
            ["--token", "a", "--other", "b", "--secret", "c"],
            ["--token", _PLACEHOLDER, "--other", "b", "--secret", _PLACEHOLDER],
            id="multiple-flags-only-sensitive-values-masked",
        ),
        pytest.param(
            ["--token", "a=b"],
            ["--token", _PLACEHOLDER],
            id="consumed-value-with-equals-masked-whole",
        ),
        pytest.param(
            ["--other", "--token", "abc"],
            ["--other", "--token", _PLACEHOLDER],
            id="sensitive-flag-after-non-sensitive",
        ),
    ],
)
def test_sanitize_command(command: list[str], expected: list[str]) -> None:
    assert sanitize_command(command, sensitive_flags=_SENSITIVE_FLAGS) == expected


@pytest.mark.parametrize(
    "command,expected",
    [
        pytest.param(
            ["rclone", "--s3-secret", "abc"],
            ["rclone", "--s3-secret", _PLACEHOLDER],
            id="backend-prefixed-space-separated",
        ),
        pytest.param(
            ["rclone", "--s3-secret=abc"],
            ["rclone", f"--s3-secret={_PLACEHOLDER}"],
            id="backend-prefixed-equals-form",
        ),
        pytest.param(
            ["rclone", "--secretive", "abc"],
            ["rclone", "--secretive", "abc"],
            id="similar-but-unsensitive-flag-passthrough",
        ),
        pytest.param(
            ["rclone", "-token", "abc"],
            ["rclone", "-token", "abc"],
            id="single-dash-flag-not-matched",
        ),
        pytest.param(
            ["copy", "my-token", "dst"],
            ["copy", "my-token", "dst"],
            id="bare-word-suffix-not-matched-as-flag",
        ),
    ],
)
def test_sanitize_command_flag_matching(command: list[str], expected: list[str]) -> None:
    assert sanitize_command(command, sensitive_flags=_SENSITIVE_FLAGS) == expected


def test_sanitize_command_does_not_mutate_input() -> None:
    command = ["--token", "abc"]
    result = sanitize_command(command, sensitive_flags=_SENSITIVE_FLAGS)
    assert command == ["--token", "abc"]
    assert result is not command
