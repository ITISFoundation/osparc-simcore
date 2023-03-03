import pytest
from servicelib.rabbitmq_errors import (
    RPCNamespaceInvalidCharsError,
    RPCNamespaceTooLongError,
)
from servicelib.rabbitmq_utils import get_namespace


@pytest.mark.parametrize(
    "entries, expected",
    [
        ({"test": "b"}, "test_b"),
        ({"hello": "1", "b": "2"}, "b_2-hello_1"),
    ],
)
def test_get_namespace(entries: dict[str, str], expected: str):
    assert get_namespace(entries) == expected


def test_get_namespace_sorts_elements():
    assert get_namespace({"1": "a", "2": "b"}) == get_namespace({"2": "b", "1": "a"})


def test_get_namespace_too_long():
    with pytest.raises(RPCNamespaceTooLongError) as exec_info:
        get_namespace({f"test{i}": f"test{i}" for i in range(11)})
    assert "contains 133 characters" in f"{exec_info.value}"


def test_get_namespace_invalid_chars():
    with pytest.raises(RPCNamespaceInvalidCharsError) as exec_info:
        get_namespace({"test": "^"})
    assert "contains not allowed characters" in f"{exec_info.value}"
