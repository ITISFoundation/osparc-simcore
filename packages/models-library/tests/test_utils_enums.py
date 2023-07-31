from enum import auto

from models_library.utils.enums import StrAutoEnum


class _Ordinal(StrAutoEnum):
    NORTH = auto()
    EAST = auto()
    SOUTH = auto()
    WEST = auto()


def test_strautoenum():
    assert [f"{n}" for n in _Ordinal] == ["NORTH", "EAST", "SOUTH", "WEST"]
