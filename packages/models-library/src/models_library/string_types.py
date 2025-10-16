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
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|TRUNCATE|MERGE|GRANT|REVOKE|COMMIT|ROLLBACK|DECLARE|CAST|CONVERT)\b|--|;|/\*|\*/|')",
    re.IGNORECASE,
)
_JS_INJECTION_PATTERN: Final[re.Pattern] = re.compile(
    r"(<\s*script.*?>|</\s*script\s*>|<\s*iframe.*?>|</\s*iframe\s*>|<\s*object.*?>|</\s*object\s*>|<\s*embed.*?>|</\s*embed\s*>|<\s*link[^>]*href\s*=\s*[\"']?\s*javascript:|vbscript:|javascript:|data:text/html|&#x6A;avascript:|&#106;avascript:|<\s*img[^>]*onerror\s*=|<\s*svg[^>]*onload\s*=|on[a-z]+\s*=)",
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


SearchPatternSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[^\%]+$",
    ),
    AfterValidator(validate_input_safety),
    annotated_types.doc(
        """
        A safe string used for search patterns.
        Strips whitespaces and enforces a length between 1 and 200 characters.
        Ensures that the input does not contain percent signs (%) to prevent wildcard searches.
        Additionally, it validates the input to ensure it does not contain potentially unsafe content such as SQL
        or JavaScript injection patterns.
        """
    ),
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
        Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs SILENTLY,
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
        Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs SILENTLY,
        i.e. without raising errors.
        """
    ),
]

#  --- tag color string (hex format) ---

ColorStr = Annotated[
    str,
    StringConstraints(pattern=re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")),
]
