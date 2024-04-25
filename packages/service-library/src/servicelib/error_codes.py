""" osparc ERROR CODES (OEC)
  Unique identifier of an exception instance
  Intended to report a user about unexpected errors.
    Unexpected exceptions can be traced by matching the
    logged error code with that appeneded to the user-friendly message

SEE test_error_codes for some use cases
"""


import re
from typing import TYPE_CHECKING

from pydantic.tools import parse_obj_as
from pydantic.types import constr

_LABEL = "OEC:{}"
_PATTERN = r"OEC:\d+"

if TYPE_CHECKING:
    ErrorCodeStr = str
else:
    ErrorCodeStr = constr(strip_whitespace=True, regex=_PATTERN)


def create_error_code(exception: BaseException) -> ErrorCodeStr:
    return parse_obj_as(ErrorCodeStr, _LABEL.format(id(exception)))


def parse_error_code(obj) -> set[ErrorCodeStr]:
    return set(re.findall(_PATTERN, f"{obj}"))
