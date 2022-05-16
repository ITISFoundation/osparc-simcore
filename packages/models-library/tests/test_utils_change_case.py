# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.utils.change_case import (
    camel_to_snake,
    snake_to_camel,
    snake_to_upper_camel,
)


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("snAke_Fun", "snakeFun"),
        ("", ""),
        # since it assumes snake, notice how these cases get flatten
        ("camelAlready", "camelalready"),
        ("AlmostCamel", "almostcamel"),
        ("_S", "S"),
        # From https://github.com/autoferrit/python-change-case/blob/master/change_case/change_case.py#L317
        ("snakes_on_a_plane", "snakesOnAPlane"),
        ("Snakes_On_A_Plane", "snakesOnAPlane"),
        ("snakes_On_a_Plane", "snakesOnAPlane"),
        ("snakes_on_A_plane", "snakesOnAPlane"),
        ("i_phone_hysteria", "iPhoneHysteria"),
        ("i_Phone_Hysteria", "iPhoneHysteria"),
    ],
)
def test_snake_to_camel(subject, expected):
    assert snake_to_camel(subject) == expected


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("snakesOnAPlane", "snakes_on_a_plane"),
        ("SnakesOnAPlane", "snakes_on_a_plane"),
        ("IPhoneHysteria", "i_phone_hysteria"),
        ("iPhoneHysteria", "i_phone_hysteria"),
    ],
)
def test_camel_to_snake(subject, expected):
    # WARNING: not always reversable
    assert camel_to_snake(subject) == expected


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("snakes_on_a_plane", "SnakesOnAPlane"),
        ("Snakes_On_A_Plane", "SnakesOnAPlane"),
        ("snakes_On_a_Plane", "SnakesOnAPlane"),
        ("snakes_on_A_plane", "SnakesOnAPlane"),
        ("i_phone_hysteria", "IPhoneHysteria"),
        ("i_Phone_Hysteria", "IPhoneHysteria"),
    ],
)
def test_snake_to_upper_camel(subject, expected):
    assert snake_to_upper_camel(subject) == expected
