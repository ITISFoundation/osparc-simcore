from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import BaseModel, Field, StrictInt


class MyModel(BaseModel):
    a: int
    b: int | None = Field(...)
    c: int = 42
    d: int | None = None
    e: int = Field(default=324, description="optional non-nullable")


def test_schema():
    assert MyModel.model_json_schema() == {
        "title": "MyModel",
        "type": "object",
        "properties": {
            "a": {"title": "A", "type": "integer"},
            "b": {"anyOf": [{"type": "integer"}, {"type": "null"}], "title": "B"},
            "c": {"title": "C", "default": 42, "type": "integer"},
            "d": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "default": None,
                "title": "D",
            },
            "e": {
                "default": 324,
                "title": "E",
                "type": "integer",
                "description": "optional non-nullable",
            },
        },
        "required": ["a", "b"],
    }


def test_only_required():
    model = MyModel(a=1, b=2)
    assert model.model_dump() == {"a": 1, "b": 2, "c": 42, "d": None, "e": 324}
    assert model.model_dump(exclude_unset=True) == {"a": 1, "b": 2}


def test_parse_obj_or_none():
    assert parse_obj_or_none(StrictInt, 42) == 42
    assert parse_obj_or_none(StrictInt, 3.14) is None
