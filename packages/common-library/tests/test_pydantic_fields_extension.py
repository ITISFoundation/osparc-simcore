from typing import Any, Callable, Literal

import pytest
from common_library.pydantic_fields_extension import get_type, is_literal, is_nullable
from pydantic import BaseModel, Field


class MyModel(BaseModel):
    a: int
    b: float | None = Field(...)
    c: str = "bla"
    d: bool | None = None
    e: Literal["bla"]


@pytest.mark.parametrize(
    "fn,expected,name",
    [
        (
            get_type,
            int,
            "a",
        ),
        (
            get_type,
            float,
            "b",
        ),
        (
            get_type,
            str,
            "c",
        ),
        (get_type, bool, "d"),
        (
            is_literal,
            False,
            "a",
        ),
        (
            is_literal,
            False,
            "b",
        ),
        (
            is_literal,
            False,
            "c",
        ),
        (is_literal, False, "d"),
        (is_literal, True, "e"),
        (
            is_nullable,
            False,
            "a",
        ),
        (
            is_nullable,
            True,
            "b",
        ),
        (
            is_nullable,
            False,
            "c",
        ),
        (is_nullable, True, "d"),
        (is_nullable, False, "e"),
    ],
)
def test_field_fn(fn: Callable[[Any], Any], expected: Any, name: str):
    assert expected == fn(MyModel.model_fields[name])
