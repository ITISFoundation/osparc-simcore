from typing import Any

import pytest
from pydantic import TypeAdapter
from simcore_service_dynamic_scheduler.api.frontend._common.base_display_model import (
    BaseUpdatableDisplayModel,
)


class Pet(BaseUpdatableDisplayModel):
    name: str
    species: str


class Friend(BaseUpdatableDisplayModel):
    name: str
    age: int


class RemderOnPropertyValueChange(BaseUpdatableDisplayModel):
    @staticmethod
    def get_rerender_on_value_change() -> set[str]:
        return {"companion"}

    name: str
    age: int
    companion: Pet | Friend


class RenderOnPropertyTypeChange(BaseUpdatableDisplayModel):
    @staticmethod
    def get_rerender_on_type_change() -> set[str]:
        return {"companion"}

    name: str
    age: int
    companion: Pet | Friend


@pytest.mark.parametrize(
    "class_, initial_dict, update_dict, requires_rerender, expected_dict",
    [
        pytest.param(
            Pet,
            {"name": "Fluffy", "species": "cat"},
            {"name": "Fido", "species": "dog"},
            False,
            {"name": "Fido", "species": "dog"},
            id="does-not-require-rerender-without-any-render-on-declared",
        ),
        pytest.param(
            RemderOnPropertyValueChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {"age": 31, "companion": {"name": "Fido", "species": "dog"}},
            True,
            {
                "name": "Alice",
                "age": 31,
                "companion": {"name": "Fido", "species": "dog"},
            },
            id="requires-rerender-on-property-change",
        ),
        pytest.param(
            RemderOnPropertyValueChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            False,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            id="do-not-require-rerender-if-same-value",
        ),
        pytest.param(
            RenderOnPropertyTypeChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {"age": 31, "companion": {"name": "Fido", "species": "dog"}},
            False,
            {
                "name": "Alice",
                "age": 31,
                "companion": {"name": "Fido", "species": "dog"},
            },
            id="does-not-require-rerender-if-same-type-with-value-changes",
        ),
        pytest.param(
            RenderOnPropertyTypeChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            False,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            id="does-not-require-rerender-if-same-type-with-NO-value-changes",
        ),
        pytest.param(
            RenderOnPropertyTypeChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {"age": 31, "companion": {"name": "Charlie", "age": 25}},
            True,
            {"name": "Alice", "age": 31, "companion": {"name": "Charlie", "age": 25}},
            id="requires-rerender-when-type-changes",
        ),
    ],
)
def test_base_updatable_display_model(
    class_: type[BaseUpdatableDisplayModel],
    initial_dict: dict[str, Any],
    update_dict: dict[str, Any],
    requires_rerender: bool,
    expected_dict: dict[str, Any],
):
    person = TypeAdapter(class_).validate_python(initial_dict)
    assert person.model_dump() == initial_dict

    assert person.requires_rerender(update_dict) is requires_rerender

    person.update(update_dict)
    assert person.model_dump() == expected_dict
