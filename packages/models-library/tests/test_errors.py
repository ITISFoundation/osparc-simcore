# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.errors import ErrorDict
from pydantic import BaseModel, ValidationError, conint


def test_pydantic_error_dict():
    class B(BaseModel):
        y: list[int]

    class A(BaseModel):
        x: conint(ge=2)
        b: B

    with pytest.raises(ValidationError) as exc_info:
        A(x=-1, b={"y": [0, "wrong"]})

    assert isinstance(exc_info.value, ValidationError)

    # demos ValidationError.errors() work
    errors: list[ErrorDict] = exc_info.value.errors()
    assert len(errors) == 2

    # checks ErrorDict interface
    for error in errors:
        # pylint: disable=no-member
        assert set(error.keys()).issuperset(ErrorDict.__required_keys__)

    def _copy(d, exclude):
        return {k: v for k, v in d.items() if k not in exclude}

    assert _copy(errors[0], exclude={"msg"}) == {
        "loc": ("x",),
        # "msg": "ensure this value is...equal to 2",
        "type": "value_error.number.not_ge",
        "ctx": {"limit_value": 2},
    }
    assert _copy(errors[1], exclude={"msg"}) == {
        "loc": ("b", "y", 1),
        # "msg": "value is not a valid integer",
        "type": "type_error.integer",
    }
