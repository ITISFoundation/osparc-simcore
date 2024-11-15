import pytest
from models_library.basic_types import IDStr
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_classes,
)
from models_library.utils.json_serialization import json_dumps
from pydantic import BaseModel, Extra, Field, Json, ValidationError, validator


class ReferenceOrderQueryParamsClass(BaseModel):
    # NOTE: this class is a copy of `FolderListSortParams` from
    # services/web/server/src/simcore_service_webserver/folders/_models.py
    # and used as a reference in these tests to ensure the same functionality

    # pylint: disable=unsubscriptable-object
    order_by: Json[OrderBy] = Field(
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        description="Order by field (modified_at|name|description) and direction (asc|desc). The default sorting order is ascending.",
        example='{"field": "name", "direction": "desc"}',
        alias="order_by",
    )

    @validator("order_by", check_fields=False)
    @classmethod
    def _validate_order_by_field(cls, v):
        if v.field not in {
            "modified_at",
            "name",
            "description",
        }:
            msg = f"We do not support ordering by provided field {v.field}"
            raise ValueError(msg)
        if v.field == "modified_at":
            v.field = "modified"
        return v

    class Config:
        extra = Extra.forbid


def test_ordering_query_model_class_factory():
    BaseOrderingQueryModel, _ = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    # inherits to add extra post-validator
    class OrderQueryParamsModel(BaseOrderingQueryModel):
        @validator("order_by", pre=True)
        @classmethod
        def _validate_order_by_field(cls, v):
            # Adds aliases!?
            if v and v.get("field") == "modified_at":
                v["field"] = "modified"
            return v

    # normal
    data = {"order_by": {"field": "modified_at", "direction": "asc"}}
    model = OrderQueryParamsModel.parse_obj(data)

    assert model.order_by
    assert model.order_by.dict() == {"field": "modified", "direction": "asc"}

    # test against reference
    expected = ReferenceOrderQueryParamsClass.parse_obj(
        {"order_by": json_dumps({"field": "modified_at", "direction": "asc"})}
    )
    assert expected.dict() == model.dict()


def test_ordering_query_model_class__fails_with_invalid_fields():

    OrderQueryParamsModel, _ = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    # fails with invalid field to sort
    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.parse_obj({"order_by": {"field": "INVALID"}})

    error = err_info.value.errors()[0]

    assert error["type"] == "value_error"
    assert "INVALID" in error["msg"]
    assert error["loc"] == ("order_by", "field")


def test_ordering_query_model_class__fails_with_invalid_direction():
    OrderQueryParamsModel, _ = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.parse_obj(
            {"order_by": {"field": "modified", "direction": "INVALID"}}
        )

    error = err_info.value.errors()[0]

    assert error["type"] == "type_error.enum"
    assert error["loc"] == ("order_by", "direction")


@pytest.mark.parametrize("override_direction_default", [True, False])
def test_ordering_query_model_class__defaults(override_direction_default: bool):

    OrderQueryParamsModel, _ = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        override_direction_default=override_direction_default,
    )

    # checks  all defaults
    model = OrderQueryParamsModel()
    assert model.order_by
    assert model.order_by.field == "modified"
    assert model.order_by.direction == OrderDirection.DESC

    # partial defaults
    model = OrderQueryParamsModel.parse_obj({"order_by": {"field": "name"}})
    assert model.order_by
    assert model.order_by.field == "name"
    assert (
        model.order_by.direction == OrderDirection.DESC
        if override_direction_default
        else OrderBy.__fields__["direction"].default
    )

    # direction alone is invalid
    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.parse_obj({"order_by": {"direction": "asc"}})

    error = err_info.value.errors()[0]
    assert error["loc"] == ("order_by", "field")
    assert error["type"] == "value_error.missing"


def test_ordering_query_model_class__openapi_generator():

    _, OrderQueryParamsModelOpenApi = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
    )

    print(OrderQueryParamsModelOpenApi.schema_json(indent=1))

    schema = OrderQueryParamsModelOpenApi.schema()

    assert schema["type"] == "object"
    assert "order_by" in schema["properties"]

    assert schema["properties"]["order_by"]["type"] == "string"
    assert schema["properties"]["order_by"]["format"] == "json-string"
    assert schema["properties"]["order_by"].get("description")
    assert schema["properties"]["order_by"].get("title")
