from unittest.mock import Mock

import pytest
from pydantic import NonNegativeInt, TypeAdapter
from simcore_service_dynamic_scheduler.api.frontend._common.base_display_model import (
    BaseUpdatableDisplayModel,
    CompleteModelDict,
)


class Pet(BaseUpdatableDisplayModel):
    name: str
    species: str


class Friend(BaseUpdatableDisplayModel):
    name: str
    age: int


class RenderOnPropertyValueChange(BaseUpdatableDisplayModel):
    name: str
    age: int
    companion: Pet | Friend


class RenderOnPropertyTypeChange(BaseUpdatableDisplayModel):
    name: str
    age: int
    companion: Pet | Friend


@pytest.mark.parametrize(
    "class_, initial_dict, update_dict, expected_dict, on_type_change, on_value_change",
    [
        pytest.param(
            Pet,
            {"name": "Fluffy", "species": "cat"},
            {"name": "Fido", "species": "dog"},
            {"name": "Fido", "species": "dog"},
            {},
            {},
            id="does-not-require-rerender-without-any-render-on-declared",
        ),
        pytest.param(
            RenderOnPropertyValueChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fido", "species": "dog"},
            },
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fido", "species": "dog"},
            },
            {},
            {"companion": 1},
            id="requires-rerender-on-property-change",
        ),
        pytest.param(
            RenderOnPropertyValueChange,
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
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {},
            {"companion": 0},
            id="do-not-require-rerender-if-same-value",
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
                "age": 31,
                "companion": {"name": "Fido", "species": "dog"},
            },
            {
                "name": "Alice",
                "age": 31,
                "companion": {"name": "Fido", "species": "dog"},
            },
            {"companion": 0},
            {},
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
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {"companion": 0},
            {},
            id="does-not-require-rerender-if-same-type-with-NO-value-changes",
        ),
        pytest.param(
            RenderOnPropertyTypeChange,
            {
                "name": "Alice",
                "age": 30,
                "companion": {"name": "Fluffy", "species": "cat"},
            },
            {"name": "Alice", "age": 31, "companion": {"name": "Charlie", "age": 25}},
            {"name": "Alice", "age": 31, "companion": {"name": "Charlie", "age": 25}},
            {"companion": 1},
            {},
            id="requires-rerender-when-type-changes",
        ),
    ],
)
def test_base_updatable_display_model(
    class_: type[BaseUpdatableDisplayModel],
    initial_dict: CompleteModelDict,
    update_dict: CompleteModelDict,
    expected_dict: CompleteModelDict,
    on_type_change: dict[str, NonNegativeInt],
    on_value_change: dict[str, NonNegativeInt],
):
    person = TypeAdapter(class_).validate_python(initial_dict)
    assert person.model_dump() == initial_dict

    subscribed_on_type_changed: dict[str, Mock] = {}
    for attribute in on_type_change:
        mock = Mock()
        person.on_type_change(attribute, mock)
        subscribed_on_type_changed[attribute] = mock

    subscribed_on_value_change: dict[str, Mock] = {}
    for attribute in on_value_change:
        mock = Mock()
        person.on_value_change(attribute, mock)
        subscribed_on_value_change[attribute] = mock

    person.update(TypeAdapter(class_).validate_python(update_dict))
    assert person.model_dump() == expected_dict

    for attribute, mock in subscribed_on_type_changed.items():
        assert (
            mock.call_count == on_type_change[attribute]
        ), f"wrong on_type_change count for '{attribute}'"

    for attribute, mock in subscribed_on_value_change.items():
        assert (
            mock.call_count == on_value_change[attribute]
        ), f"wrong on_value_change count for '{attribute}'"
