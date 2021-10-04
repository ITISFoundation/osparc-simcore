from pathlib import Path
from typing import Any

import pytest
from models_library.generics import DataEnveloped, DictBaseModel


def test_dict_base_model():
    some_dict = {
        "a key": 123,
        "another key": "a string value",
        "yet another key": Path("some_path"),
    }
    some_instance = DictBaseModel[str, Any].parse_obj(some_dict)
    assert some_instance

    # test some typical dict methods
    assert len(some_instance) == 3
    for k, k2 in zip(some_dict, some_instance):
        assert k == k2

    for k, k2 in zip(some_dict.keys(), some_instance.keys()):
        assert k == k2

    for v, v2 in zip(some_dict.values(), some_instance.values()):
        assert v == v2

    for i, i2 in zip(some_dict.items(), some_instance.items()):
        assert i == i2

    assert some_instance.get("a key") == 123
    assert some_instance.get("a non existing key") is None

    assert some_instance["a key"] == 123
    with pytest.raises(KeyError):
        some_instance["a non existing key"]  # pylint: disable=pointless-statement
    some_instance["a new key"] = 23
    assert some_instance["a new key"] == 23


def test_data_enveloped():
    some_enveloped_string = DataEnveloped[str]()
    assert some_enveloped_string
    assert not some_enveloped_string.data
    assert not some_enveloped_string.error

    some_enveloped_float = DataEnveloped[float](data=232.44)
    assert some_enveloped_float
    assert some_enveloped_float.data == 232.44
    assert not some_enveloped_float.error

    some_enveloped_bool = DataEnveloped[bool](error="some error happened")
    assert some_enveloped_bool
    assert not some_enveloped_bool.data
    assert some_enveloped_bool.error == "some error happened"

    with pytest.raises(ValueError):
        DataEnveloped[int](data=213, error="some error message")
