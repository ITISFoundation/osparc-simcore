import datetime
import warnings
from datetime import timedelta

from pydantic import TypeAdapter, field_validator


def validate_numeric_string_as_timedelta(field: str):
    """Transforms a float/int number into a valid datetime as it used to work in the past"""

    def _numeric_string_as_timedelta(
        v: datetime.timedelta | str | float,
    ) -> datetime.timedelta | str | float:
        if isinstance(v, str):
            try:
                converted_value = float(v)

                iso8601_format = TypeAdapter(timedelta).dump_python(
                    timedelta(seconds=converted_value), mode="json"
                )
                warnings.warn(
                    f"{field}='{v}' -should be set to-> {field}='{iso8601_format}' (ISO8601 datetime format). "
                    "Please also convert the value in the >>OPS REPOSITORY<<. "
                    "For details: https://docs.pydantic.dev/1.10/usage/types/#datetime-types.",
                    DeprecationWarning,
                    stacklevel=8,
                )

                return converted_value
            except ValueError:
                # returns format like "1:00:00"
                return v
        return v

    return field_validator(field, mode="before")(_numeric_string_as_timedelta)
