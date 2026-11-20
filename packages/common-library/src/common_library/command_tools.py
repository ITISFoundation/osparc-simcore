from collections.abc import Collection, Sequence
from typing import Final

_PLACEHOLDER: Final[str] = "*" * 8


def _is_sensitive_flag(flag: str, sensitive_flags: Collection[str]) -> bool:
    """True for a listed flag or a backend-prefixed variant (e.g. '--s3-access-key-id' for '--access-key-id')."""
    return any(flag == name or flag.endswith(f"-{name.removeprefix('--')}") for name in sensitive_flags)


def sanitize_command(
    command: Sequence[str],
    *,
    sensitive_flags: Collection[str],
) -> list[str]:
    """Masks the values of sensitive flags so a command list can be logged safely.

    A flag token matches an entry of `sensitive_flags` either exactly or as a
    backend-prefixed variant, e.g. '--s3-access-key-id' matches '--access-key-id'.
    A token of the form ``--flag=value`` keeps its flag part and replaces the value.
    A sensitive flag written as a separate token always consumes the following token
    as its value, even when that token starts with '-'. The input is not modified.
    """
    sanitized: list[str] = []
    skip_indices: set[int] = set()

    for i, arg in enumerate(command):
        if i in skip_indices:
            continue

        if "=" in arg:
            flag_part = arg.split("=", 1)[0]
            sanitized.append(f"{flag_part}={_PLACEHOLDER}" if _is_sensitive_flag(flag_part, sensitive_flags) else arg)
        elif _is_sensitive_flag(arg, sensitive_flags):
            sanitized.append(arg)
            if i + 1 < len(command):
                sanitized.append(_PLACEHOLDER)
                skip_indices.add(i + 1)
        else:
            sanitized.append(arg)

    return sanitized
