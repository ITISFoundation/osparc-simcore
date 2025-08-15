import pytest
from pytest_simcore.helpers.assert_checks import assert_equal_ignoring_none


@pytest.mark.parametrize(
    "expected, actual",
    [
        ({"a": 1, "b": 2}, {"a": 1, "b": 2, "c": 3}),
        ({"a": 1, "b": None}, {"a": 1, "b": 42}),
        ({"a": {"x": 10, "y": None}}, {"a": {"x": 10, "y": 99}}),
        ({"a": {"x": 10, "y": 20}}, {"a": {"x": 10, "y": 20, "z": 30}}),
        ({}, {"foo": "bar"}),
    ],
)
def test_assert_equal_ignoring_none_passes(expected, actual):
    assert_equal_ignoring_none(expected, actual)

@pytest.mark.parametrize(
    "expected, actual, error_msg",
    [
        ({"a": 1, "b": 2}, {"a": 1}, "Missing key b"),
        ({"a": 1, "b": 2}, {"a": 1, "b": 3}, "Mismatch in b: 3 != 2"),
        ({"a": {"x": 10, "y": 20}}, {"a": {"x": 10, "y": 99}}, "Mismatch in y: 99 != 20"),
        ({"a": {"x": 10}}, {"a": {}}, "Missing key x"),
    ],
)
def test_assert_equal_ignoring_none_fails(expected, actual, error_msg):
    with pytest.raises(AssertionError) as exc_info:
        assert_equal_ignoring_none(expected, actual)
    assert error_msg in str(exc_info.value)
