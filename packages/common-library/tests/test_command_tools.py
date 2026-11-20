from typing import Final

import pytest
from common_library.command_tools import sanitize_command

_PLACEHOLDER: Final[str] = "*" * 8


def _is_sensitive(flag: str) -> bool:
    return flag in {"--token", "--secret"}


def _is_sensitive_prefix(flag: str) -> bool:
    return flag.startswith("--secret")


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
    assert sanitize_command(command, is_sensitive_flag=_is_sensitive) == expected


def test_sanitize_command_predicate_injection() -> None:
    command = ["--secret-access-key", "key", "--token", "abc"]
    assert sanitize_command(command, is_sensitive_flag=_is_sensitive_prefix) == [
        "--secret-access-key",
        _PLACEHOLDER,
        "--token",
        "abc",
    ]


def test_sanitize_command_custom_placeholder() -> None:
    assert sanitize_command(["--token", "abc"], is_sensitive_flag=_is_sensitive, placeholder="REDACTED") == [
        "--token",
        "REDACTED",
    ]


def test_sanitize_command_does_not_mutate_input() -> None:
    command = ["--token", "abc"]
    result = sanitize_command(command, is_sensitive_flag=_is_sensitive)
    assert command == ["--token", "abc"]
    assert result is not command
