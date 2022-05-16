# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.utils.string_formatters import snake_to_camel


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("snAke_Fun", "snakeFun"),
        ("", ""),
        # since it assumes snake, notice how these cases get flatten
        ("camelAlready", "camelalready"),
        ("AlmostCamel", "almostcamel"),
        ("_S", "S"),
    ],
)
def test_snake_to_camel(subject, expected):
    assert snake_to_camel(subject) == expected
