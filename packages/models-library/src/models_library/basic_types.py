from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, TypeAlias

from pydantic import AfterValidator, Field, HttpUrl, PositiveInt, StringConstraints
from pydantic_core import PydanticCustomError
from pydantic.json_schema import JsonSchemaValue

from .basic_regex import (
    PROPERTY_KEY_RE,
    SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS,
    SIMPLE_VERSION_RE,
    UUID_RE,
)

NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]

PositiveDecimal = Annotated[Decimal, Field(gt=0)]

# Used for amounts like credits or dollars
# NOTE: upper limit to avoid https://github.com/ITISFoundation/appmotion-exchange/issues/2
# NOTE: do not contraint in decimal places. Too strong validation error rather Decimal.quantize
# before passing the value
AmountDecimal = Annotated[Decimal, Field(gt=0, lt=1e6)]

# port number range
PortInt = Annotated[int, Field(gt=0, lt=65535)]

# e.g. 'v5'
VersionTag = Annotated[str, StringConstraints(pattern=r"^v\d$")]

VersionStr = Annotated[str, StringConstraints(pattern=SIMPLE_VERSION_RE)]

# e.g. '1.23.11' or '2.1.0-rc2' or not 0.1.0-alpha  (see test_SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
SemanticVersionStr = Annotated[
    str, StringConstraints(pattern=SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
]

# checksums
# sha1sum path/to/file
SHA1Str = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{40}$")]

# sha256sum path/to/file
SHA256Str = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

# md5sum path/to/file
MD5Str = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{32}$")]

# env var
EnvVarKey = Annotated[str, StringConstraints(pattern=r"[a-zA-Z]\w*")]

# e.g. '5c833a78-1af3-43a7-9ed7-6a63b188f4d8'
UUIDStr = Annotated[str, StringConstraints(pattern=UUID_RE)]

# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
_ELLIPSIS_CHAR: Final[str] = "..."


class IDStr(str, StringConstraints):
    strip_whitespace: bool = True
    min_length: int = 1
    max_length: int = 100

    def __new__(cls, value: str) -> "IDStr":
        # Apply the constraints before creating the new instance
        if cls.strip_whitespace:
            value = value.strip()

        if len(value) < cls.min_length:
            raise PydanticCustomError('string_too_short', f"IDStr is too short: {value}")

        if len(value) > cls.max_length:
            raise PydanticCustomError('string_too_long', f"IDStr is too long: {value}")

        return str.__new__(cls, value)

    @classmethod
    def concatenate(cls, *args: str, link_char: str = " ") -> "IDStr":
        result = link_char.join(args).strip()

        max_length = cls.max_length
        min_length = cls.min_length

        if len(result) > max_length:
            if max_length > len(_ELLIPSIS_CHAR):
                result = (
                    result[: max_length - len(_ELLIPSIS_CHAR)].rstrip()
                    + _ELLIPSIS_CHAR
                )
            else:
                result = _ELLIPSIS_CHAR[0] * max_length

        if len(result) < min_length:
            raise ValueError(f"IDStr.concatenate: result is too short: {result}")

        return cls(result)


# NOTE: Use to input e.g. titles or display names
# A truncated string:
#   - Strips whitespaces and truncate strings that exceed the specified characters limit (curtail_length).
#   - Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs silently, i.e. without raising errors.
# SEE https://github.com/ITISFoundation/osparc-simcore/pull/5989#discussion_r1650506583
ShortTruncatedStr = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(lambda x: x[:600])
]

# NOTE: Use to input e.g. descriptions or summaries
# Analogous to ShortTruncatedStr
LongTruncatedStr = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(lambda x: x[:65536])
]  # same as github descripton

# auto-incremented primary-key IDs
IdInt: TypeAlias = PositiveInt
PrimaryKeyInt: TypeAlias = PositiveInt


# https e.g. https://techterms.com/definition/https
class HttpSecureUrl(HttpUrl):
    allowed_schemes = {"https"}


class HttpUrlWithCustomMinLength(HttpUrl):
    # Overwriting min length to be back compatible when generating OAS
    min_length = 0


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BootModeEnum(StrEnum):
    """
    Values taken by SC_BOOT_MODE environment variable
    set in Dockerfile and used during docker/boot.sh
    """

    DEFAULT = "default"
    LOCAL = "local-development"
    DEBUG = "debug"
    PRODUCTION = "production"
    DEVELOPMENT = "development"

    def is_devel_mode(self) -> bool:
        """returns True if this boot mode is used for development"""
        return self in (self.DEBUG, self.DEVELOPMENT, self.LOCAL)


class BuildTargetEnum(StrEnum):
    """
    Values taken by SC_BUILD_TARGET environment variable
    set in Dockerfile that defines the stage targeted in the
    docker image build
    """

    BUILD = "build"
    CACHE = "cache"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


KeyIDStr = Annotated[str, StringConstraints(pattern=PROPERTY_KEY_RE)]
