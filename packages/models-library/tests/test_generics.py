from pathlib import Path
from typing import Any

import pytest
from faker import Faker
from models_library.generics import DictModel, Envelope
from pydantic import ValidationError


def test_dict_base_model():
    some_dict = {
        "a key": 123,
        "another key": "a string value",
        "yet another key": Path("some_path"),
    }
    some_instance = DictModel[str, Any].parse_obj(some_dict)
    assert some_instance

    # test some typical dict methods
    assert len(some_instance) == 3
    for k, k2 in zip(some_dict, some_instance, strict=False):
        assert k == k2

    for k, k2 in zip(some_dict.keys(), some_instance.keys(), strict=False):
        assert k == k2

    for v, v2 in zip(some_dict.values(), some_instance.values(), strict=False):
        assert v == v2

    for i, i2 in zip(some_dict.items(), some_instance.items(), strict=False):
        assert i == i2

    assert some_instance.get("a key") == 123
    assert some_instance.get("a non existing key") is None

    assert some_instance["a key"] == 123
    with pytest.raises(KeyError):
        some_instance["a non existing key"]  # pylint: disable=pointless-statement
    some_instance["a new key"] = 23
    assert some_instance["a new key"] == 23


def test_data_enveloped(faker: Faker):
    some_enveloped_string = Envelope[str]()
    assert some_enveloped_string
    assert not some_enveloped_string.data
    assert not some_enveloped_string.error

    random_float = faker.pyfloat()
    some_enveloped_float = Envelope[float](data=random_float)
    assert some_enveloped_float
    assert some_enveloped_float.data == random_float
    assert not some_enveloped_float.error

    random_text = faker.text()
    some_enveloped_bool = Envelope[bool](error=random_text)
    assert some_enveloped_bool
    assert not some_enveloped_bool.data
    assert some_enveloped_bool.error == random_text


def test_enveloped_data_dict():
    # error
    with pytest.raises(ValidationError) as err_info:
        Envelope[dict](data="not-a-dict")

    error: ValidationError = err_info.value
    assert error.errors() == [
        {
            "loc": ("data",),
            "msg": "value is not a valid dict",
            "type": "type_error.dict",
        }
    ]

    # empty dict
    enveloped = Envelope[dict](data={})
    assert enveloped.data == {}
    assert enveloped.error is None
