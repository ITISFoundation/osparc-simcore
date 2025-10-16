import re
from typing import Annotated, Final, TypeAlias

import annotated_types
from pydantic import AfterValidator, StringConstraints

from .utils.common_validators import trim_string_before

# --- heuristics ---
SQL_INJECTION_PATTERN = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\b|--|;|'|\")",
    re.IGNORECASE,
)
JS_INJECTION_PATTERN = re.compile(
    r"(<script.*?>|</script>|on\w+\s*=|javascript:)", re.IGNORECASE
)

MIN_DESCRIPTION_LENGTH = 3  # minimum length for description strings without whitespaces


def _validate_input_safety(value: str) -> str:
    # reject likely injection content
    if SQL_INJECTION_PATTERN.search(value) or JS_INJECTION_PATTERN.search(value):
        msg = "Potentially unsafe content detected."
        raise ValueError(msg)
    return value


def _strip_all_whitespaces(value: str) -> str:
    # normalize whitespaces
    return re.sub(r"\s+", " ", value).strip()


DescriptionSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=MIN_DESCRIPTION_LENGTH),
    AfterValidator(_validate_input_safety),
]


_SHORT_TRUNCATED_STR_MAX_LENGTH: Final[int] = 600
ShortTruncatedStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    trim_string_before(max_length=_SHORT_TRUNCATED_STR_MAX_LENGTH),
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

_LONG_TRUNCATED_STR_MAX_LENGTH: Final[int] = 65536  # same as github description
LongTruncatedStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    trim_string_before(max_length=_LONG_TRUNCATED_STR_MAX_LENGTH),
    annotated_types.doc(
        """
        A truncated string used to input e.g. descriptions or summaries.
        Strips whitespaces and truncate strings that exceed the specified characters limit (curtail_length).
        Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs silently,
        i.e. without raising errors.
        """
    ),
]
