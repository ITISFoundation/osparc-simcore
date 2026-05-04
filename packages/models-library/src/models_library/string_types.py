import re
from typing import Annotated, Final, NamedTuple, TypeAlias

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


STRING_UNSAFE_CONTENT_ERROR_CODE: Final[str] = "string_unsafe_content"


class XSSPattern(NamedTuple):
    pattern: re.Pattern
    message: str


_SAFE_XSS_PATTERNS: Final[list[XSSPattern]] = [
    # === Lightweight, non-backtracking safe checks (bounded / literal / simple alternations) ===
    XSSPattern(
        re.compile(r"(?i)<\s*(?:script|iframe|object|embed|link|meta|base)\b"),
        "Contains potentially dangerous HTML tags",
    ),
    XSSPattern(
        re.compile(r"(?i)</\s*(?:script|iframe|object|embed|link|meta|base)\s*>"),
        "Contains potentially dangerous HTML closing tags",
    ),
    XSSPattern(
        re.compile(
            r"(?i)\b(?:src|href|xlink:href|srcdoc)\s*=\s*(?:['\"]\s*)?(?:javascript:|vbscript:|data:)",
            re.IGNORECASE,
        ),
        "Contains unsafe URL protocols in attributes",
    ),
    XSSPattern(
        re.compile(r"(?i)javascript%3a|vbscript%3a|data%3a"),
        "Contains encoded malicious protocols",
    ),
    XSSPattern(
        re.compile(
            r"(?ix)&#\s*(?:x[0-9a-f]{1,6}|[0-9]{1,6})\s*;\s*(?:javascript:|vbscript:|data:)",
            re.IGNORECASE,
        ),
        "Contains encoded characters followed by unsafe protocols",
    ),
    XSSPattern(
        re.compile(r"(?i)\bon[a-z]{1,20}\s*="),
        "Contains inline event handlers",
    ),
    XSSPattern(
        re.compile(
            r"(?ix)style\s*=\s*['\"][^'\"]{0,500}\b(?:expression\(|url\s*\()",
            re.IGNORECASE,
        ),
        "Contains potentially dangerous CSS expressions",
    ),
    XSSPattern(
        re.compile(
            r"(?ix)<\s*(?:img|svg)\b[^>]{0,500}\b(?:src|xlink:href)\s*=\s*['\"]?(?:javascript:|data:)",
            re.IGNORECASE,
        ),
        "Contains unsafe protocols in image or SVG tags",
    ),
    XSSPattern(
        re.compile(
            r"(?ix)<\s*meta\b[^>]{0,200}\bhttp-equiv\s*=\s*['\"]?refresh['\"]?",
            re.IGNORECASE,
        ),
        "Contains meta refresh directives",
    ),
    XSSPattern(
        re.compile(r"(?i)\bsrcdoc\s*=\s*['\"]"),
        "Contains srcdoc attribute which may execute arbitrary HTML",
    ),
    XSSPattern(
        re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]"),
        "Contains control or invisible characters",
    ),
    XSSPattern(
        re.compile(r"(?i)(\$\{[^}]{0,200}\}|\#\{[^}]{0,200}\}|<%[^%]{0,200}%>|{{[^}]{0,200}})"),
        "Contains template injection patterns",
    ),
    XSSPattern(
        re.compile(r"(?i)\bvbscript\s*:"),
        "Contains VBScript protocol",
    ),
]


def _contains_percent_or_entity_obfuscation(value_lower: str) -> bool:
    # simple substring checks — no heavy regex backtracking
    if "javascript%3a" in value_lower or "vbscript%3a" in value_lower or "data%3a" in value_lower:
        return True
    return "data:text/html" in value_lower


def _contains_obfuscated_protocol_by_normalization(value_lower: str) -> bool:
    # remove ALL non-alphanumeric chars for maximum normalization
    # this catches heavily spaced out patterns like "j a v a s c r i p t:"
    norm = re.sub(r"[^a-z0-9]", "", value_lower)
    return (
        "javascript" in norm
        or "vbscript" in norm
        or "datatext" in norm
        or "data:" in value_lower  # keep original check for data: protocol
    )


def validate_input_xss_safety(value: str) -> str:
    # Run fast, simple regex checks first (fail-fast).
    for xss_pattern in _SAFE_XSS_PATTERNS:
        if xss_pattern.pattern.search(value):
            raise PydanticCustomError(
                STRING_UNSAFE_CONTENT_ERROR_CODE,
                "{msg}",
                {"msg": xss_pattern.message},
            )

    value_lower = value.lower()
    # Fast substring / percent-encoding checks (no backtracking risk)
    if _contains_percent_or_entity_obfuscation(value_lower):
        raise PydanticCustomError(
            STRING_UNSAFE_CONTENT_ERROR_CODE,
            "Contains encoded malicious content",
            {},
        )

    # Normalization-based obfuscation detection (de-duplicates heavy regex)
    if _contains_obfuscated_protocol_by_normalization(value_lower):
        raise PydanticCustomError(
            STRING_UNSAFE_CONTENT_ERROR_CODE,
            "Contains obfuscated unsafe protocols",
            {},
        )

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
        pattern=r"^[A-Za-z0-9 ._-]+$",
        # CAREFUL: string that ONLY contains alphanumeric characters, spaces, dots, underscores, or hyphens
    ),
    AfterValidator(validate_input_xss_safety),
    annotated_types.doc(
        """ A safe string used in **name identifiers**, It might be very restrictive for display names (e.g. titles or labels) """
    ),
]

DisplaySafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
    ),
    AfterValidator(validate_input_xss_safety),
    annotated_types.doc(""" Like `NameSafeStr` but more suited for display names"""),
]

DescriptionSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=MIN_DESCRIPTION_LENGTH,
        max_length=MAX_DESCRIPTION_LENGTH,
    ),
    AfterValidator(validate_input_xss_safety),
]


GlobPatternSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=200,
        strip_whitespace=True,
        pattern=r"^[A-Za-z0-9 ._\*@-]*$",  # Allow alphanumeric, spaces, dots, underscores, hyphens, asterisks and at signs
        to_lower=True,  # make case-insensitive
    ),
    AfterValidator(validate_input_xss_safety),
]


SearchPatternSafeStr: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9 ._@-]*$",  # Allow alphanumeric, spaces, dots, underscores, hyphens, and at signs
        to_lower=True,  # make case-insensitive
    ),
    AfterValidator(validate_input_xss_safety),
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
    AfterValidator(validate_input_xss_safety),
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
    AfterValidator(validate_input_xss_safety),
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
