# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path
from typing import Any

import pytest
from faker import Faker
from models_library.generics import DictModel, Envelope
from pydantic import BaseModel, ValidationError
from pydantic.version import version_short


def test_dict_base_model():
    some_dict = {
        "a key": 123,
        "another key": "a string value",
        "yet another key": Path("some_path"),
    }
    some_instance = DictModel[str, Any].model_validate(some_dict)
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


def test_enveloped_error_str(faker: Faker):
    random_text = faker.text()
    some_enveloped_bool = Envelope[bool](error=random_text)
    assert some_enveloped_bool
    assert not some_enveloped_bool.data
    assert some_enveloped_bool.error == random_text


@pytest.fixture
def builtin_value(faker: Faker, builtin_type: type) -> Any:
    return {
        "str": faker.pystr(),
        "float": faker.pyfloat(),
        "int": faker.pyint(),
        "bool": faker.pybool(),
        "dict": faker.pydict(),
        "tuple": faker.pytuple(),
        "set": faker.pyset(),
    }[builtin_type.__name__]


@pytest.mark.parametrize(
    "builtin_type", [str, float, int, bool, tuple, set], ids=lambda x: x.__name__
)
def test_enveloped_data_builtin(builtin_type: type, builtin_value: Any):
    # constructors
    envelope = Envelope[builtin_type](data=builtin_value)

    assert envelope == Envelope[builtin_type].from_data(builtin_value)

    # exports
    assert envelope.model_dump(exclude_unset=True, exclude_none=True) == {
        "data": builtin_value
    }
    assert envelope.model_dump() == {"data": builtin_value, "error": None}


def test_enveloped_data_model():
    class User(BaseModel):
        idr: int
        name: str = "Jane Doe"

    enveloped = Envelope[User](data={"idr": 3})

    assert isinstance(enveloped.data, User)
    assert enveloped.model_dump(exclude_unset=True, exclude_none=True) == {
        "data": {"idr": 3}
    }


def test_enveloped_data_dict():
    # error
    with pytest.raises(ValidationError) as err_info:
        Envelope[dict](data="not-a-dict")

    error: ValidationError = err_info.value
    assert error.errors() == [
        {
            "input": "not-a-dict",
            "loc": ("data",),
            "msg": "Input should be a valid dictionary",
            "type": "dict_type",
            "url": f"https://errors.pydantic.dev/{version_short()}/v/dict_type",
        }
    ]

    # empty dict
    enveloped = Envelope[dict](data={})
    assert enveloped.data == {}
    assert enveloped.error is None


def test_enveloped_data_list():
    # error
    with pytest.raises(ValidationError) as err_info:
        Envelope[list](data="not-a-list")

    error: ValidationError = err_info.value
    assert error.errors() == [
        {
            "input": "not-a-list",
            "loc": ("data",),
            "msg": "Input should be a valid list",
            "type": "list_type",
            "url": f"https://errors.pydantic.dev/{version_short()}/v/list_type",
        }
    ]

    # empty list
    enveloped = Envelope[list](data=[])
    assert enveloped.data == []
    assert enveloped.error is None
