import datetime

from models_library.services_types import RunID
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


def timedelta_try_convert_str_to_float(field: str):
    """Transforms a float/int number into a valid datetime as it used to work in the past"""
    return field_validator(field, mode="before")(_try_convert_str_to_float_or_return)


def _convert_str_to_run_id_object(v: RunID | str) -> RunID:
    if isinstance(v, str):
        return RunID(v)
    return v


def convert_str_to_run_id_object(field: str):
    return field_validator(field, mode="before")(_convert_str_to_run_id_object)
