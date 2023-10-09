from collections.abc import Iterable
from typing import TypeVar

from openpyxl.utils import get_column_letter
from pydantic import BaseModel

T = TypeVar("T")


def ensure_correct_instance(
    template_data: BaseModel, class_to_check_against: type[T]
) -> T:
    if not isinstance(template_data, class_to_check_against):
        msg = (
            f"Expected '{class_to_check_against.__name__}', but "
            f"'{template_data.__class__.__name__}' was provided"
        )
        raise TypeError(msg)

    return template_data


def get_max_array_length(*arrays_of_elements) -> int:
    return max(len(x) for x in arrays_of_elements)


def column_generator(start_from: int, elements: int) -> Iterable[str]:
    """maps columns index to letters"""
    for column_index in range(start_from, start_from + elements):
        yield get_column_letter(column_index)
