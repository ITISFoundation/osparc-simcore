"""osparc ERROR CODES (OEC)
  Unique identifier of an exception instance
  Intended to report a user about unexpected errors.
    Unexpected exceptions can be traced by matching the
    logged error code with that appeneded to the user-friendly message

SEE test_error_codes for some use cases
"""

import hashlib
import re
import traceback
from datetime import UTC, datetime
from typing import Annotated, Final, TypeAlias

from pydantic import StringConstraints, TypeAdapter

_LABEL = "OEC:{fingerprint}-{timestamp}"

_LEN = 12  # chars (~48 bits)
_NAMED_PATTERN = re.compile(
    r"OEC:(?P<fingerprint>[a-fA-F0-9]{12})-(?P<timestamp>\d{13,14})"
    # NOTE: timestamp limits: 13 digits (from 2001), 14 digits (good for ~500+ years)
)
_PATTERN = re.compile(r"OEC:[a-fA-F0-9]{12}-\d{13,14}")


ErrorCodeStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=_NAMED_PATTERN)
]


def _create_fingerprint(exc: BaseException) -> str:
    """
    Unique error fingerprint of the **traceback** for deduplication purposes
    """
    tb = traceback.extract_tb(exc.__traceback__)
    frame_sigs = [f"{frame.name}:{frame.lineno}" for frame in tb]
    fingerprint = f"{type(exc).__name__}|" + "|".join(frame_sigs)
    # E.g. ZeroDivisionError|foo:23|main:10
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:_LEN]


_SECS_TO_MILISECS: Final[int] = 1000  # ms


def _create_timestamp() -> int:
    """Timestamp as milliseconds since epoch
    NOTE: this reduces the precission to milliseconds but it is good enough for our purpose
    """
    ts = datetime.now(UTC).timestamp() * _SECS_TO_MILISECS
    return int(ts)

_LEN = 12  # chars (~48 bits)


def _generate_error_fingerprint(exc: BaseException) -> str:
    """
    Unique error fingerprint for deduplication purposes
    """
    tb = traceback.extract_tb(exc.__traceback__)
    frame_sigs = [f"{frame.name}:{frame.lineno}" for frame in tb]
    fingerprint = f"{type(exc).__name__}|" + "|".join(frame_sigs)
    # E.g. ZeroDivisionError|foo:23|main:10
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:_LEN]


def create_error_code(exception: BaseException) -> ErrorCodeStr:
    """
    Generates a unique error code for the given exception.

    The error code follows the format: `OEC:{traceback}-{timestamp}`.
    This code is intended to be shared with the front-end as a `SupportID`
    for debugging and support purposes.
    """
    return TypeAdapter(ErrorCodeStr).validate_python(
        _LABEL.format(
            fingerprint=_create_fingerprint(exception),
            timestamp=_create_timestamp(),
        )
    )


def parse_error_codes(obj) -> list[ErrorCodeStr]:
    return TypeAdapter(list[ErrorCodeStr]).validate_python(_PATTERN.findall(f"{obj}"))


def parse_error_code_parts(oec: ErrorCodeStr) -> tuple[str, datetime]:
    """Returns traceback-fingerprint and timestamp from `OEC:{traceback}-{timestamp}`"""
    match = _NAMED_PATTERN.match(oec)
    if not match:
        msg = f"Invalid error code format: {oec}"
        raise ValueError(msg)
    fingerprint = match.group("fingerprint")
    timestamp = datetime.fromtimestamp(
        float(match.group("timestamp")) / _SECS_TO_MILISECS, tz=UTC
    )
    return fingerprint, timestamp
