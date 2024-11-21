# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.errors import ErrorDict
from pydantic import BaseModel, Field, ValidationError
from pydantic.version import version_short
from typing_extensions import Annotated


def test_pydantic_error_dict():
    class B(BaseModel):
        y: list[int]

    class A(BaseModel):
        x: Annotated[int, Field(ge=2)]
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
        "ctx": {"ge": 2},
        "input": -1,
        "loc": ("x",),
        "type": "greater_than_equal",
        "url": f"https://errors.pydantic.dev/{version_short()}/v/greater_than_equal",
    }
    assert _copy(errors[1], exclude={"msg"}) == {
        "input": "wrong",
        "loc": ("b", "y", 1),
        "type": "int_parsing",
        "url": f"https://errors.pydantic.dev/{version_short()}/v/int_parsing",
    }
