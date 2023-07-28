from enum import Enum, unique
from typing import Any


@unique
class StrAutoEnum(str, Enum):  # noqa: SLOT000
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()


def enum_to_dict(enum_cls: type[Enum]) -> dict[str, Any]:
    return {m.name: m.value for m in enum_cls}


def check_equivalency(enum_lhs: type[Enum], enum_rhs: type[Enum]) -> bool:
    return enum_to_dict(enum_lhs) == enum_to_dict(enum_rhs)
