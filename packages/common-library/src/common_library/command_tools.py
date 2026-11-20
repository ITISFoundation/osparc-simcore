from collections.abc import Callable, Sequence
from typing import Annotated, Final

from annotated_types import doc

_PLACEHOLDER: Final[str] = "*" * 8

type SensitiveFlagPredicate = Annotated[
    Callable[[str], bool],
    doc("returns True for a flag token whose value must be masked, e.g. '--rc-pass'"),
]


def sanitize_command(
    command: Sequence[str],
    *,
    is_sensitive_flag: SensitiveFlagPredicate,
    placeholder: str = _PLACEHOLDER,
) -> list[str]:
    """Masks the values of sensitive flags so a command list can be logged safely.

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
            sanitized.append(f"{flag_part}={placeholder}" if is_sensitive_flag(flag_part) else arg)
        elif is_sensitive_flag(arg):
            sanitized.append(arg)
            if i + 1 < len(command):
                sanitized.append(placeholder)
                skip_indices.add(i + 1)
        else:
            sanitized.append(arg)

    return sanitized
