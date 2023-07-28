from enum import Enum, unique

import pytest
from models_library.utils.enums import check_equivalency, enum_to_dict
from pydantic import BaseModel, ValidationError, parse_obj_as

#
# Enum Color1 is **equivalent** to enum Color2 but not equal
#


@unique
class Color1(Enum):
    RED = "RED"


@unique
class Color2(Enum):
    RED = "RED"


def test_equivalent_enums_are_not_strictly_equal():
    assert Color1 != Color2

    assert enum_to_dict(Color1) == enum_to_dict(Color2)

    assert check_equivalency(Color1, Color2)
    assert check_equivalency(Color1, Color1)


#
# Here two equivalent enum BUT of type str-enum
#
# SEE from models_library.utils.enums.AutoStrEnum
#


@unique
class ColorStrAndEnum1(str, Enum):
    RED = "RED"


@unique
class ColorStrAndEnum2(str, Enum):
    RED = "RED"


def test_enums_vs_strenums():
    # here are the differences
    assert f"{Color1.RED}" == "Color1.RED"
    assert f"{ColorStrAndEnum1.RED}" == "RED"

    assert Color1.RED != "RED"
    assert ColorStrAndEnum1.RED == "RED"

    assert Color1.RED != ColorStrAndEnum1.RED

    # here are the analogies
    assert Color1.RED.name == "RED"
    assert ColorStrAndEnum1.RED.name == "RED"

    assert Color1.RED.value == "RED"
    assert ColorStrAndEnum1.RED.value == "RED"


#
# How are these parsed/exported in pydantic?
# https://docs.pydantic.dev/dev-v2/usage/types/enums/
#


def test_equivalent_enums_in_pydantic():
    class Model(BaseModel):
        color: Color1

    model = parse_obj_as(Model, {"color": Color1.RED})
    assert model.color == Color1.RED

    # Can parse from string
    model = parse_obj_as(Model, {"color": "RED"})
    assert model.color == Color1.RED

    # Can NOT parse from equilalent enum
    with pytest.raises(ValidationError):
        parse_obj_as(Model, {"color": Color2.RED})

    #
    # Using str-enums allow you to parse from equivalent enums!
    #

    class ModelStrAndEnum(BaseModel):
        color: ColorStrAndEnum1

    assert check_equivalency(Color1, ColorStrAndEnum1)

    model = parse_obj_as(ModelStrAndEnum, {"color": ColorStrAndEnum1.RED})
    assert model.color == ColorStrAndEnum1.RED

    # Can parse from string
    model = parse_obj_as(ModelStrAndEnum, {"color": "RED"})
    assert model.color == ColorStrAndEnum1.RED

    # Can parse other equivalent str-enum!
    parse_obj_as(ModelStrAndEnum, {"color": ColorStrAndEnum2.RED})

    # Can still NOT parse equilalent enum(-only)
    with pytest.raises(ValidationError):
        parse_obj_as(ModelStrAndEnum, {"color": Color1.RED})

    # And the opposite? NO!!!
    with pytest.raises(ValidationError):
        parse_obj_as(Color1, {"color": ColorStrAndEnum1.RED})

    with pytest.raises(ValidationError):
        parse_obj_as(Color1, {"color": ColorStrAndEnum2.RED})
