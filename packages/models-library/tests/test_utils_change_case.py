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
        # WARNING: the algorithm does not check if the subject is already camelcase.
        # It will flatten the output like you can see in these examples.
        ("camelAlready", "camelalready"),
        ("AlmostCamel", "almostcamel"),
        ("_S", "S"),
        # NOTE : that conversion is not always reversable (non-injective)
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
        ("already_snake", "already_snake"),
        # NOTE : that conversion is not always reversable (non-injective)
        ("snakesOnAPlane", "snakes_on_a_plane"),
        ("SnakesOnAPlane", "snakes_on_a_plane"),
        ("IPhoneHysteria", "i_phone_hysteria"),
        ("iPhoneHysteria", "i_phone_hysteria"),
    ],
)
def test_camel_to_snake(subject, expected):
    assert camel_to_snake(subject) == expected


@pytest.mark.parametrize(
    "subject,expected",
    [
        # NOTE : that conversion is not always reversable (non-injective)
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
