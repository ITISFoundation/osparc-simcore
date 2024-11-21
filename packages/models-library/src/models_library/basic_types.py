from decimal import Decimal
from enum import Enum
from re import Pattern
from typing import Annotated, ClassVar, Final, TypeAlias

from common_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from pydantic import Field, HttpUrl, PositiveInt, StringConstraints
from pydantic_core import core_schema

from .basic_regex import (
    PROPERTY_KEY_RE,
    SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS,
    SIMPLE_VERSION_RE,
    UUID_RE,
)

assert issubclass(LogLevel, Enum)  # nosec
assert issubclass(BootModeEnum, Enum)  # nosec
assert issubclass(BuildTargetEnum, Enum)  # nosec

__all__: tuple[str, ...] = (
    "LogLevel",
    "BootModeEnum",
    "BuildTargetEnum",
)


NonNegativeDecimal: TypeAlias = Annotated[Decimal, Field(ge=0)]

PositiveDecimal: TypeAlias = Annotated[Decimal, Field(gt=0)]

# Used for amounts like credits or dollars
# NOTE: upper limit to avoid https://github.com/ITISFoundation/appmotion-exchange/issues/2
# NOTE: do not contraint in decimal places. Too strong validation error rather Decimal.quantize
# before passing the value
AmountDecimal: TypeAlias = Annotated[Decimal, Field(gt=0, lt=1e6)]

# port number range
PortInt: TypeAlias = Annotated[int, Field(gt=0, lt=65535)]


# https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers#Registered_ports
RegisteredPortInt: TypeAlias = Annotated[int, Field(gt=1024, lt=65535)]


# e.g. 'v5'
VersionTag: TypeAlias = Annotated[str, StringConstraints(pattern=r"^v\d$")]

VersionStr: TypeAlias = Annotated[str, StringConstraints(pattern=SIMPLE_VERSION_RE)]

# e.g. '1.23.11' or '2.1.0-rc2' or not 0.1.0-alpha  (see test_SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
SemanticVersionStr: TypeAlias = Annotated[
    str, StringConstraints(pattern=SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
]

# checksums
# sha1sum path/to/file
SHA1Str: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{40}$")]

# sha256sum path/to/file
SHA256Str: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

# md5sum path/to/file
MD5Str: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{32}$")]

# env var
EnvVarKey: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z]\w*")]

# e.g. '5c833a78-1af3-43a7-9ed7-6a63b188f4d8'
UUIDStr: TypeAlias = Annotated[str, StringConstraints(pattern=UUID_RE)]


# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
_ELLIPSIS_CHAR: Final[str] = "..."


class ConstrainedStr(str):
    pattern: str | Pattern[str] | None = None
    min_length: int | None = None
    max_length: int | None = None
    strip_whitespace: bool = False
    curtail_length: int | None = None

    @classmethod
    def _validate(cls, __input_value: str) -> str:
        if cls.curtail_length and len(__input_value) > cls.curtail_length:
            __input_value = __input_value[: cls.curtail_length]
        return cls(__input_value)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(
                pattern=cls.pattern,
                min_length=cls.min_length,
                max_length=cls.max_length,
                strip_whitespace=cls.strip_whitespace,
            ),
        )


class IDStr(ConstrainedStr):
    strip_whitespace = True
    min_length = 1
    max_length = 100

    @staticmethod
    def concatenate(*args: "IDStr", link_char: str = " ") -> "IDStr":
        result = link_char.join(args).strip()
        assert IDStr.min_length  # nosec
        assert IDStr.max_length  # nosec
        if len(result) > IDStr.max_length:
            if IDStr.max_length > len(_ELLIPSIS_CHAR):
                result = (
                    result[: IDStr.max_length - len(_ELLIPSIS_CHAR)].rstrip()
                    + _ELLIPSIS_CHAR
                )
            else:
                result = _ELLIPSIS_CHAR[0] * IDStr.max_length
        if len(result) < IDStr.min_length:
            msg = f"IDStr.concatenate: result is too short: {result}"
            raise ValueError(msg)
        return IDStr(result)


class ShortTruncatedStr(ConstrainedStr):
    # NOTE: Use to input e.g. titles or display names
    # A truncated string:
    #   - Strips whitespaces and truncate strings that exceed the specified characters limit (curtail_length).
    #   - Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs silently, i.e. without raising errors.
    # SEE https://github.com/ITISFoundation/osparc-simcore/pull/5989#discussion_r1650506583
    strip_whitespace = True
    curtail_length = 600


class LongTruncatedStr(ConstrainedStr):
    # NOTE: Use to input e.g. descriptions or summaries
    # Analogous to ShortTruncatedStr
    strip_whitespace = True
    curtail_length = 65536  # same as github descripton


# auto-incremented primary-key IDs
IdInt: TypeAlias = PositiveInt
PrimaryKeyInt: TypeAlias = PositiveInt


# https e.g. https://techterms.com/definition/https
class HttpSecureUrl(HttpUrl):
    allowed_schemes: ClassVar[set[str]] = {"https"}


class HttpUrlWithCustomMinLength(HttpUrl):
    # Overwriting min length to be back compatible when generating OAS
    min_length = 0


KeyIDStr = Annotated[str, StringConstraints(pattern=PROPERTY_KEY_RE)]
