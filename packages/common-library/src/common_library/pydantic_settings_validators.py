import datetime

from pydantic import field_validator


def _get_float_string_as_seconds(
    v: datetime.timedelta | str | float,
) -> datetime.timedelta | float | str:
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            # returns format like "1:00:00"
            return v
    return v


def validate_timedelta_in_legacy_mode(field: str):
    """Transforms a float/int number into a valid datetime as it used to work in the past"""
    return field_validator(field, mode="before")(_get_float_string_as_seconds)
