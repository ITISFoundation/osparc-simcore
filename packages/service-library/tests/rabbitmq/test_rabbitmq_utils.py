import pytest
from pydantic import ValidationError
from servicelib.rabbitmq import RPCNamespace


@pytest.mark.parametrize(
    "entries, expected",
    [
        ({"test": "b"}, "test_b"),
        ({"hello": "1", "b": "2"}, "b_2-hello_1"),
    ],
)
def test_rpc_namespace_from_entries(entries: dict[str, str], expected: str):
    assert RPCNamespace.from_entries(entries) == expected


def test_rpc_namespace_sorts_elements():
    assert RPCNamespace.from_entries({"1": "a", "2": "b"}) == RPCNamespace.from_entries(
        {"2": "b", "1": "a"}
    )


def test_rpc_namespace_too_long():
    with pytest.raises(ValidationError) as exec_info:
        RPCNamespace.from_entries({f"test{i}": f"test{i}" for i in range(20)})
    assert "ensure this value has at most 252 characters" in f"{exec_info.value}"


def test_rpc_namespace_too_short():
    with pytest.raises(ValidationError) as exec_info:
        RPCNamespace.from_entries({})
    assert "ensure this value has at least 1 characters" in f"{exec_info.value}"


def test_rpc_namespace_invalid_symbols():
    with pytest.raises(ValidationError) as exec_info:
        RPCNamespace.from_entries({"test": "@"})
    assert "string does not match regex" in f"{exec_info.value}"
