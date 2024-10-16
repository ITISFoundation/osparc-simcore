from models_library.services_types import RunID
from pydantic import field_validator


def _convert_str_to_run_id_object(v: RunID | str) -> RunID:
    if isinstance(v, str):
        return RunID(v)
    return v


def convert_str_to_run_id_object(field: str):
    return field_validator(field, mode="before")(_convert_str_to_run_id_object)
