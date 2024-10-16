import datetime

from pydantic import field_validator


def _try_convert_str_to_float_or_return(
    v: datetime.timedelta | str | float,
) -> datetime.timedelta | str | float:
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            # returns format like "1:00:00"
            return v
    return v


def validate_timedelta_in_legacy_mode(field: str):
    """Transforms a float/int number into a valid datetime as it used to work in the past"""
    return field_validator(field, mode="before")(_try_convert_str_to_float_or_return)
