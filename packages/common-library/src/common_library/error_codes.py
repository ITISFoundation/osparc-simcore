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
from typing import TYPE_CHECKING, Annotated

from pydantic import StringConstraints, TypeAdapter

_LABEL = "OEC:{}"
_PATTERN = r"OEC:[a-zA-Z0-9]+"

if TYPE_CHECKING:
    ErrorCodeStr = str
else:
    ErrorCodeStr = Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=_PATTERN)
    ]

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
    return TypeAdapter(ErrorCodeStr).validate_python(
        _LABEL.format(_generate_error_fingerprint(exception))
    )


def parse_error_code(obj) -> set[ErrorCodeStr]:
    return set(re.findall(_PATTERN, f"{obj}"))
