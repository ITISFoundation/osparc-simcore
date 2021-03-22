from typing import List, Dict, Any, Type
from pydantic import BaseModel


def ensure_same_field_length(
    fields_to_check: List[str], values: Dict[str, Any]
) -> None:
    field_lengths = {field: values.get(field, -1) for field in fields_to_check}
    # expecting one single entry in a set if all lengths are the same
    if len(set(field_lengths.values())) != 1:
        raise ValueError(
            f"Not all fields had the same length, please check {field_lengths}"
        )


def ensure_correct_instance(
    template_data: BaseModel, class_to_check_against: Type[BaseModel]
) -> BaseModel:
    if not isinstance(template_data, class_to_check_against):
        raise ValueError(
            (
                f"Expected '{class_to_check_against.__name__}', but "
                f"'{template_data.__class__.__name__}' was provided"
            )
        )

    return template_data