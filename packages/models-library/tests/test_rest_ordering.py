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
        default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
        description="Order by field (modified_at|name|description) and direction (asc|desc). The default sorting order is ascending.",
        example='{"field": "name", "direction": "desc"}',
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
            v.field = "modified_column"
        return v

    class Config:
        extra = Extra.forbid


def test_ordering_query_model_class_factory():
    BaseOrderingQueryModel = create_ordering_query_model_classes(
        ordering_fields={"modified_at", "name", "description"},
        default=OrderBy(field=IDStr("modified_at"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={"modified_at": "modified_column"},
    )

    # inherits to add extra post-validator
    class OrderQueryParamsModel(BaseOrderingQueryModel):
        ...

    # normal
    data = {"order_by": {"field": "modified_at", "direction": "asc"}}
    model = OrderQueryParamsModel.parse_obj(data)

    assert model.order_by
    assert model.order_by.dict() == {"field": "modified_column", "direction": "asc"}

    # test against reference
    expected = ReferenceOrderQueryParamsClass.parse_obj(
        {"order_by": json_dumps({"field": "modified_at", "direction": "asc"})}
    )
    assert expected.dict() == model.dict()


def test_ordering_query_model_class__fails_with_invalid_fields():

    OrderQueryParamsModel = create_ordering_query_model_classes(
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
    OrderQueryParamsModel = create_ordering_query_model_classes(
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


def test_ordering_query_model_class__defaults():

    OrderQueryParamsModel = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={"modified": "modified_at"},
    )

    # checks  all defaults
    model = OrderQueryParamsModel()
    assert model.order_by
    assert model.order_by.field == "modified_at"  # NOTE that this was mapped!
    assert model.order_by.direction == OrderDirection.DESC

    # partial defaults
    model = OrderQueryParamsModel.parse_obj({"order_by": {"field": "name"}})
    assert model.order_by
    assert model.order_by.field == "name"
    assert model.order_by.direction == OrderBy.__fields__["direction"].default

    # direction alone is invalid
    with pytest.raises(ValidationError) as err_info:
        OrderQueryParamsModel.parse_obj({"order_by": {"direction": "asc"}})

    error = err_info.value.errors()[0]
    assert error["loc"] == ("order_by", "field")
    assert error["type"] == "value_error.missing"


def test_ordering_query_model_with_map():
    OrderQueryParamsModel = create_ordering_query_model_classes(
        ordering_fields={"modified", "name", "description"},
        default=OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC),
        ordering_fields_api_to_column_map={"modified": "some_db_column_name"},
    )

    model = OrderQueryParamsModel.parse_obj({"order_by": {"field": "modified"}})
    assert model.order_by.field == "some_db_column_name"
