from re import Pattern
from typing import Annotated, Final, TypeAlias

from pydantic import Field
from pydantic_core import core_schema

# https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers#Registered_ports
RegisteredPortInt: TypeAlias = Annotated[int, Field(gt=1024, lt=65535)]

# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
_ELLIPSIS_CHAR: Final[str] = "..."


class ConstrainedStr(str):  # noqa: SLOT000
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
