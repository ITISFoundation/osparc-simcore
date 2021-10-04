from pathlib import Path
from typing import Any

import pytest
from models_library.generics import DictBaseModel


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
