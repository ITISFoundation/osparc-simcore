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

_LABEL_TEMPLATE = "OEC:{}"
_LABEL_PATTERN = r"OEC:\d+"

if TYPE_CHECKING:
    ErrorCodeStr = str
else:
    ErrorCodeStr = constr(strip_whitespace=True, regex=_LABEL_PATTERN)


def create_error_code(exception: Exception) -> ErrorCodeStr:
    return parse_obj_as(ErrorCodeStr, _LABEL_TEMPLATE.format(id(exception)))


def parse_error_code(obj) -> set[ErrorCodeStr]:
    return set(re.findall(_LABEL_PATTERN, f"{obj}"))
