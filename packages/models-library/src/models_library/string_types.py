import re
from typing import Annotated, Final, TypeAlias

import annotated_types
from pydantic import (
    AfterValidator,
    StringConstraints,
)
from pydantic_core import PydanticCustomError

from .utils.common_validators import trim_string_before

# --- shared heuristics ---
MIN_DESCRIPTION_LENGTH: Final[int] = 3
MAX_DESCRIPTION_LENGTH: Final[int] = 5000
MAX_NAME_LENGTH: Final[int] = 100

_SHORT_TRUNCATED_STR_MAX_LENGTH: Final[int] = 600
_LONG_TRUNCATED_STR_MAX_LENGTH: Final[int] = 65536  # same as github descriptions

_SQL_INJECTION_PATTERN: Final[re.Pattern] = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\b|--|;|'|\")",
    re.IGNORECASE,
)
_JS_INJECTION_PATTERN: Final[re.Pattern] = re.compile(
    r"(<\s*script.*?>|</\s*script\s*>|on\w+\s*=|javascript:|data:text/html)",
    re.IGNORECASE,
)

STRING_UNSAFE_CONTENT_ERROR_CODE: Final[str] = "string_unsafe_content"


def validate_input_safety(value: str) -> str:
    if _SQL_INJECTION_PATTERN.search(value) or _JS_INJECTION_PATTERN.search(value):
        msg_template = "This input contains potentially unsafe content."
        raise PydanticCustomError(STRING_UNSAFE_CONTENT_ERROR_CODE, msg_template, {})
    return value


# --- core composition primitives ---
#
# `*SafeStr` types MUST be used for INPUT string fields in the external APIs
#

NameSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
        pattern=r"^[A-Za-z0-9 ._\-]+$",  # strict whitelist
    ),
    AfterValidator(validate_input_safety),
]


DescriptionSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=MIN_DESCRIPTION_LENGTH,
        max_length=MAX_DESCRIPTION_LENGTH,
    ),
    AfterValidator(validate_input_safety),
]


GlobPatternSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=200,
        strip_whitespace=True,
        pattern=r"^[^%]*$",
    ),
    AfterValidator(validate_input_safety),
]


# --- truncating string types ---
ShortTruncatedStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    trim_string_before(max_length=_SHORT_TRUNCATED_STR_MAX_LENGTH),
    AfterValidator(validate_input_safety),
    annotated_types.doc(
        """
        A truncated string used to input e.g. titles or display names.
        Strips whitespaces and truncate strings that exceed the specified characters limit (curtail_length).
        Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs silently,
        i.e. without raising errors.
        """
        # SEE https://github.com/ITISFoundation/osparc-simcore/pull/5989#discussion_r1650506583
    ),
]


LongTruncatedStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    trim_string_before(max_length=_LONG_TRUNCATED_STR_MAX_LENGTH),
    AfterValidator(validate_input_safety),
    annotated_types.doc(
        """
        A truncated string used to input e.g. descriptions or summaries.
        Strips whitespaces and truncate strings that exceed the specified characters limit (curtail_length).
        Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs silently,
        i.e. without raising errors.
        """
    ),
]
