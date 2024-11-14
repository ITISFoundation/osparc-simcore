import datetime as dt
import re
import warnings

from pydantic import TypeAdapter, field_validator


def _validate_legacy_timedelta_str(time_str: str | dt.timedelta) -> str | dt.timedelta:
    if not isinstance(time_str, str):
        return time_str

    # Match the format [-][DD ][HH:MM]SS[.ffffff]
    match = re.match(
        r"^(?P<sign>-)?(?:(?P<days>\d+)\s)?(?:(?P<hours>\d+):)?(?:(?P<minutes>\d+):)?(?P<seconds>\d+)(?P<fraction>\.\d+)?$",
        time_str,
    )
    if not match:
        return time_str

    # Extract components with defaults if not present
    sign = match.group("sign") or ""
    days = match.group("days") or "0"
    hours = match.group("hours") or "0"
    minutes = match.group("minutes") or "0"
    seconds = match.group("seconds")
    fraction = match.group("fraction") or ""

    # Convert to the format [-][DD]D[,][HH:MM:]SS[.ffffff]
    return f"{sign}{int(days)}D,{int(hours):02}:{int(minutes):02}:{seconds}{fraction}"


def validate_numeric_string_as_timedelta(field: str):
    """Transforms a float/int number into a valid datetime as it used to work in the past"""

    def _numeric_string_as_timedelta(
        v: dt.timedelta | str | float,
    ) -> dt.timedelta | str | float:
        if isinstance(v, str):
            try:
                converted_value = float(v)

                iso8601_format = TypeAdapter(dt.timedelta).dump_python(
                    dt.timedelta(seconds=converted_value), mode="json"
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
                return _validate_legacy_timedelta_str(v)
        return v

    return field_validator(field, mode="before")(_numeric_string_as_timedelta)
