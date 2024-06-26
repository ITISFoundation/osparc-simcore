import enum
import inspect
from enum import Enum, unique
from typing import Any


class auto_str(enum.auto):  # noqa: N801
    value: str = enum._auto_null  # pylint:disable=protected-access # noqa: SLF001


@unique
class StrAutoEnum(str, Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()


def enum_to_dict(enum_cls: type[Enum]) -> dict[str, Any]:
    return {m.name: m.value for m in enum_cls}


def are_equivalent_enums(enum_cls1: type[Enum], enum_cls2: type[Enum]) -> bool:
    assert inspect.isclass(enum_cls1)  # nosec
    assert issubclass(enum_cls1, Enum)  # nosec
    assert inspect.isclass(enum_cls2)  # nosec
    assert issubclass(enum_cls2, Enum)  # nosec

    try:
        return enum_to_dict(enum_cls1) == enum_to_dict(enum_cls2)

    except (AttributeError, TypeError):
        return False
