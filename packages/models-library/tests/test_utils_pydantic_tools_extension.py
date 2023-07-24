from models_library.utils.pydantic_tools_extension import (
    FieldNotRequired,
    parse_obj_or_none,
)
from pydantic import BaseModel, Field, StrictInt


class MyModel(BaseModel):
    a: int
    b: int | None = Field(...)
    c: int = 42
    d: int | None = None
    e: int = FieldNotRequired(description="optional non-nullable")


def test_schema():
    assert MyModel.schema() == {
        "title": "MyModel",
        "type": "object",
        "properties": {
            "a": {"title": "A", "type": "integer"},
            "b": {"title": "B", "type": "integer"},
            "c": {"title": "C", "default": 42, "type": "integer"},
            "d": {"title": "D", "type": "integer"},
            "e": {
                "title": "E",
                "type": "integer",
                "description": "optional non-nullable",
            },
        },
        "required": ["a", "b"],
    }


def test_only_required():
    model = MyModel(a=1, b=2)
    assert model.dict() == {"a": 1, "b": 2, "c": 42, "d": None, "e": None}
    assert model.dict(exclude_unset=True) == {"a": 1, "b": 2}


def test_parse_obj_or_none():
    assert parse_obj_or_none(StrictInt, 42) == 42
    assert parse_obj_or_none(StrictInt, 3.14) is None
